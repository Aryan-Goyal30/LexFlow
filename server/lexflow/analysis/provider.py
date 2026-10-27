"""The model behind an interface, so it can be configured or replaced.

``provider_for(settings)`` gives the configured provider, or the reason there
is none (``Unavailable``): analysis disabled, key or model missing. Nothing is
contacted when a provider is built; the first network call happens when the
worker runs an analysis.

``GeminiProvider`` uses Google's official ``google-genai`` SDK on the server
only. The key is held as a ``SecretStr`` until the client is built and never
appears in errors, logs or results: failures are mapped to fixed messages and
codes, never to the provider's own error text. The SDK's own retries are off;
the worker decides about retries (``ProviderError.retry``).

For support, a failed call also carries a small ``diagnostic``: Google's
status name and error reason code, read only from the structured fields of
the SDK's error (never from its free-text message), accepted only if they
look like such codes and are short. It goes to the worker log and to the
administrator-only audit log, not to the run's stored reason or to the API.

Messages are written for the people who read them. ``ProviderError.message``
and ``Unavailable.reason`` are shown to every staff member who can see the
case, so they never name settings, files or keys. Operator detail (which
setting to fix) is in ``Unavailable.detail``, shown to Administrators only,
and in the validated ``diagnostic`` codes.

Selection fails closed: only the providers listed in ``SUPPORTED_PROVIDERS``
can be built; any other value is reported as unsupported and never falls
through to Gemini.
"""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from pydantic import SecretStr

from lexflow.analysis.evidence import Evidence
from lexflow.config import Settings

logger = logging.getLogger("lexflow.analysis")

PROVIDER_LABELS = {
    "gemini": "Google Gemini API",
    "scripted": "Scripted test provider (not AI)",
    "prepared": "Prepared demonstration analysis (not AI)",
}
# The providers this code can build. Anything else fails closed.
SUPPORTED_PROVIDERS = frozenset({"gemini", "scripted", "prepared"})
# Shown to staff when the configuration needs an administrator.
ASK_AN_ADMINISTRATOR = "An administrator needs to check the AI configuration of this server."


@dataclass(frozen=True)
class Request:
    system_instruction: str
    prompt: str
    response_schema: dict[str, Any]
    max_output_tokens: int
    # The evidence behind the prompt. Real providers see only the prompt text;
    # the scripted test double builds its canned answer from it.
    evidence: Evidence


@dataclass(frozen=True)
class Response:
    text: str
    truncated: bool = False  # stopped at the output-token limit
    usage: dict[str, int] = field(default_factory=dict)


class ProviderError(Exception):
    """A provider call failed. ``code`` and ``message`` are safe to store and show.

    ``diagnostic`` holds validated provider codes (``httpStatus``, ``status``,
    ``reason``) for logs and the audit log only; it may be empty.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retry: bool = False,
        diagnostic: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry = retry
        self.diagnostic: dict[str, str] = dict(diagnostic or {})


@runtime_checkable
class AnalysisProvider(Protocol):
    name: str
    model: str

    def generate(self, request: Request) -> Response: ...


@dataclass(frozen=True)
class Unavailable:
    """Why analysis cannot run. ``reason`` is safe for every staff member;
    ``detail`` names the setting to fix and is for Administrators only."""

    code: str
    reason: str
    detail: str | None = None


ClientFactory = Callable[[str, int], Any]


def _default_client(api_key: str, timeout_ms: int) -> Any:
    from google import genai
    from google.genai import types

    # retry_options=None: the SDK makes one attempt; the worker owns retries.
    return genai.Client(
        api_key=api_key, http_options=types.HttpOptions(timeout=timeout_ms, retry_options=None)
    )


def _transport_errors() -> tuple[type[BaseException], ...]:
    import httpx

    errors: list[type[BaseException]] = [httpx.TimeoutException, httpx.TransportError]
    try:
        import httpx2

        errors += [httpx2.TimeoutException, httpx2.TransportError]
    except ImportError:  # pragma: no cover - httpx2 is installed with the API
        pass
    return tuple(errors)


def _timeouts() -> tuple[type[BaseException], ...]:
    import httpx

    errors: list[type[BaseException]] = [httpx.TimeoutException, TimeoutError]
    try:
        import httpx2

        errors.append(httpx2.TimeoutException)
    except ImportError:  # pragma: no cover
        pass
    return tuple(errors)


_BLOCKED_FINISH = frozenset(
    {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "LANGUAGE", "OTHER"}
)


class GeminiProvider:
    name = "gemini"

    def __init__(
        self,
        api_key: SecretStr,
        model: str,
        *,
        timeout_seconds: int,
        client_factory: ClientFactory = _default_client,
    ) -> None:
        self.model = model
        self._key = api_key
        self._timeout_ms = timeout_seconds * 1000
        self._client_factory = client_factory

    def __repr__(self) -> str:  # never shows the key
        return f"GeminiProvider(model={self.model!r})"

    def generate(self, request: Request) -> Response:
        from google.genai import errors, types

        config = types.GenerateContentConfig(
            system_instruction=request.system_instruction,
            response_mime_type="application/json",
            response_json_schema=request.response_schema,
            max_output_tokens=request.max_output_tokens,
            candidate_count=1,
        )
        try:
            client = self._client_factory(self._key.get_secret_value(), self._timeout_ms)
            response = client.models.generate_content(
                model=self.model, contents=request.prompt, config=config
            )
        except errors.APIError as exc:
            diagnostic = _diagnostic(exc)
            error = _api_error(exc.code, quota_exhausted=_quota_exhausted(exc))
            error.diagnostic = diagnostic
            raise error from None
        except _timeouts():
            raise ProviderError(
                "provider-timeout", "Google's API did not answer in time.", retry=True
            ) from None
        except _transport_errors():
            raise ProviderError(
                "provider-unreachable", "Google's API could not be reached.", retry=True
            ) from None
        return _read(response)


# google.rpc.Code names ("INVALID_ARGUMENT") and google.rpc.ErrorInfo.reason values
# ("API_KEY_INVALID": UPPER_SNAKE_CASE, at most 63 characters, per Google's API
# design guide). Anything else is discarded, never stored or logged.
_STATUS_NAME = re.compile(r"[A-Z][A-Z_]{1,39}")
_REASON_CODE = re.compile(r"[A-Z][A-Z0-9_]{1,62}")
_ERROR_INFO = "type.googleapis.com/google.rpc.ErrorInfo"
# google.rpc.QuotaFailure: which quota was exceeded. Quota ids are identifiers
# such as "GenerateRequestsPerDayPerProjectPerModel-FreeTier".
_QUOTA_FAILURE = "type.googleapis.com/google.rpc.QuotaFailure"
_QUOTA_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{1,99}")
# A quota that resets only after a day (or longer) is not worth retrying in
# minutes; a per-minute rate limit is.
_LONG_QUOTA = re.compile(r"Per(Day|Month)|Daily|Monthly", re.IGNORECASE)


def _error_body(exc: Any) -> dict[str, Any] | None:
    body = getattr(exc, "details", None)
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        body = body["error"]
    return body if isinstance(body, dict) else None


def _detail_entries(exc: Any) -> list[dict[str, Any]]:
    body = _error_body(exc)
    entries = body.get("details") if body is not None else None
    return [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []


def _quota_ids(exc: Any) -> list[str]:
    """Validated quota ids from QuotaFailure entries (structured fields only)."""
    found: list[str] = []
    for entry in _detail_entries(exc):
        if entry.get("@type") != _QUOTA_FAILURE:
            continue
        violations = entry.get("violations")
        for violation in violations if isinstance(violations, list) else []:
            quota = violation.get("quotaId") if isinstance(violation, dict) else None
            if isinstance(quota, str) and _QUOTA_ID.fullmatch(quota):
                found.append(quota)
    return found


def _quota_exhausted(exc: Any) -> bool:
    """True when a 429 names a daily or monthly quota: retrying within minutes
    cannot succeed. Without a structured QuotaFailure the answer is False, so
    an ordinary 429 keeps its retries."""
    return getattr(exc, "code", None) == 429 and any(_LONG_QUOTA.search(q) for q in _quota_ids(exc))


def _diagnostic(exc: Any) -> dict[str, str]:
    """Validated codes from the SDK error's structured fields. Never reads
    ``message`` or any other free text; returns only what passes the patterns."""
    found: dict[str, str] = {}
    http = getattr(exc, "code", None)
    if isinstance(http, int) and not isinstance(http, bool) and 100 <= http <= 599:
        found["httpStatus"] = str(http)
    status = getattr(exc, "status", None)
    if isinstance(status, str) and _STATUS_NAME.fullmatch(status):
        found["status"] = status
    for entry in _detail_entries(exc):
        if entry.get("@type") != _ERROR_INFO:
            continue
        reason = entry.get("reason")
        if isinstance(reason, str) and _REASON_CODE.fullmatch(reason):
            found["reason"] = reason
            break
    quotas = _quota_ids(exc)
    if quotas:
        found["quotaId"] = quotas[0]
    return found


def _api_error(status: int | None, *, quota_exhausted: bool = False) -> ProviderError:
    """A ProviderError whose message is safe for every staff member: it never
    names settings, files or keys (operator detail travels in ``diagnostic``)."""
    if status == 429 and quota_exhausted:
        return ProviderError(
            "provider-quota-exhausted",
            "The AI provider's usage quota for this server is used up (429), so the "
            "analysis was not retried. Start it again after the quota resets. "
            + ASK_AN_ADMINISTRATOR,
        )
    if status == 429:
        return ProviderError(
            "provider-rate-limited",
            "Google's API is limiting requests at the moment (429). Try again later.",
            retry=True,
        )
    if status in (401, 403):
        return ProviderError(
            "provider-auth-failed",
            f"Google's API did not accept this server's credentials ({status}). "
            + ASK_AN_ADMINISTRATOR,
        )
    if status == 404:
        return ProviderError(
            "provider-model-not-found",
            "Google's API does not offer the configured AI model (404). " + ASK_AN_ADMINISTRATOR,
        )
    if status is not None and status >= 500:
        return ProviderError(
            "provider-unavailable", f"Google's API had a server error ({status}).", retry=True
        )
    return ProviderError(
        "provider-rejected", f"Google's API refused the request ({status or 'no status'})."
    )


def _read(response: Any) -> Response:
    feedback = getattr(response, "prompt_feedback", None)
    if feedback is not None and getattr(feedback, "block_reason", None):
        raise ProviderError("provider-blocked", "Google's API declined to answer this request.")
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        raise ProviderError("provider-empty", "Google's API returned no answer.")
    candidate = candidates[0]
    finish = getattr(getattr(candidate, "finish_reason", None), "name", None) or str(
        getattr(candidate, "finish_reason", "") or ""
    )
    if finish in _BLOCKED_FINISH:
        raise ProviderError(
            "provider-blocked", "Google's API stopped the answer (safety or policy)."
        )
    parts = getattr(getattr(candidate, "content", None), "parts", None) or []
    text = "".join(
        p.text for p in parts if getattr(p, "text", None) and not getattr(p, "thought", False)
    )
    if not text.strip():
        raise ProviderError("provider-empty", "Google's API returned an empty answer.")
    usage: dict[str, int] = {}
    meta = getattr(response, "usage_metadata", None)
    for name, key in (
        ("prompt_token_count", "promptTokens"),
        ("candidates_token_count", "outputTokens"),
        ("thoughts_token_count", "thinkingTokens"),
        ("total_token_count", "totalTokens"),
    ):
        value = getattr(meta, name, None) if meta is not None else None
        if isinstance(value, int):
            usage[key] = value
    return Response(text=text, truncated=finish == "MAX_TOKENS", usage=usage)


def unavailable_reason(settings: Settings) -> Unavailable | None:
    """None when the configured provider can be built; otherwise why not.
    Unknown providers fail closed (``provider-unsupported``)."""
    provider = settings.ai_provider
    if provider == "disabled":
        return Unavailable(
            "analysis-disabled",
            "AI analysis is turned off on this server.",
            detail="LEXFLOW_AI_PROVIDER=disabled in server/.env.",
        )
    if provider not in SUPPORTED_PROVIDERS:
        return Unavailable(
            "provider-unsupported",
            "AI analysis is not available: the configured AI provider is not supported. "
            + ASK_AN_ADMINISTRATOR,
            detail=(
                "LEXFLOW_AI_PROVIDER names a provider this version cannot use; supported: "
                + ", ".join(sorted(SUPPORTED_PROVIDERS))
                + ", disabled."
            ),
        )
    if provider == "gemini":
        if settings.gemini_api_key is None:
            return Unavailable(
                "provider-not-configured",
                "AI analysis is not fully configured on this server. " + ASK_AN_ADMINISTRATOR,
                detail="GEMINI_API_KEY is missing from server/.env.",
            )
        if settings.gemini_model is None:
            return Unavailable(
                "provider-not-configured",
                "AI analysis is not fully configured on this server. " + ASK_AN_ADMINISTRATOR,
                detail="GEMINI_MODEL is missing from server/.env.",
            )
    return None


def configured_model(settings: Settings) -> str | None:
    if settings.ai_provider == "gemini":
        return settings.gemini_model
    if settings.ai_provider == "scripted":
        from lexflow.analysis.scripted import MODEL

        return MODEL
    if settings.ai_provider == "prepared":
        from lexflow.analysis.prepared import MODEL as PREPARED_MODEL

        return PREPARED_MODEL
    return None


def client_data_allowed(settings: Settings, case_id: uuid.UUID | None = None) -> bool:
    """May a case that is not sample data be analysed (decision D1)?

    D1 keeps client material away from external AI services until a privacy
    review. The prepared demonstration provider sends nothing anywhere (it
    runs on this computer and answers only for its own fictional case), so D1
    does not restrict it; every other provider needs LEXFLOW_AI_ALLOW_CLIENT_DATA,
    or the case's id in LEXFLOW_AI_APPROVED_CASE_IDS (approved one by one).
    """
    return (
        settings.ai_allow_client_data
        or settings.ai_provider == "prepared"
        or (case_id is not None and case_id in settings.ai_approved_case_ids)
    )


def provider_for(settings: Settings) -> AnalysisProvider | Unavailable:
    """The configured provider, or why there is none. Every provider is chosen
    by an explicit branch: an unknown name can never reach Gemini."""
    missing = unavailable_reason(settings)
    if missing is not None:
        return missing
    if settings.ai_provider == "scripted":  # settings refuse it outside test/e2e databases
        from lexflow.analysis.scripted import ScriptedProvider

        return ScriptedProvider()
    if settings.ai_provider == "prepared":  # local, written in advance: not AI
        from lexflow.analysis.prepared import PreparedProvider

        return PreparedProvider()
    if settings.ai_provider == "gemini":
        key, model = settings.gemini_api_key, settings.gemini_model
        if key is not None and model is not None:
            return GeminiProvider(key, model, timeout_seconds=settings.ai_timeout_seconds)
    return Unavailable(  # pragma: no cover - unavailable_reason covers every other case
        "provider-unsupported",
        "AI analysis is not available. " + ASK_AN_ADMINISTRATOR,
    )
