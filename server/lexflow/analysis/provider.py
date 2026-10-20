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
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from pydantic import SecretStr

from lexflow.analysis.evidence import Evidence
from lexflow.config import Settings

logger = logging.getLogger("lexflow.analysis")

PROVIDER_LABELS = {"gemini": "Google Gemini API", "scripted": "Scripted test provider (not AI)"}


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
    """A provider call failed. ``code`` and ``message`` are safe to store and show."""

    def __init__(self, code: str, message: str, *, retry: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry = retry


@runtime_checkable
class AnalysisProvider(Protocol):
    name: str
    model: str

    def generate(self, request: Request) -> Response: ...


@dataclass(frozen=True)
class Unavailable:
    code: str
    reason: str


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
            raise _api_error(exc.code) from None
        except _timeouts():
            raise ProviderError(
                "provider-timeout", "Google's API did not answer in time.", retry=True
            ) from None
        except _transport_errors():
            raise ProviderError(
                "provider-unreachable", "Google's API could not be reached.", retry=True
            ) from None
        return _read(response)


def _api_error(status: int | None) -> ProviderError:
    if status == 429:
        return ProviderError(
            "provider-rate-limited",
            "Google's API refused the request because of rate or quota limits (429).",
            retry=True,
        )
    if status in (401, 403):
        return ProviderError(
            "provider-auth-failed",
            f"Google's API refused the key ({status}). Check GEMINI_API_KEY in server/.env.",
        )
    if status == 404:
        return ProviderError(
            "provider-model-not-found",
            "Google's API does not know the configured model (404). Check GEMINI_MODEL.",
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
    if settings.ai_provider == "disabled":
        return Unavailable(
            "analysis-disabled",
            "AI analysis is turned off on this server (LEXFLOW_AI_PROVIDER=disabled).",
        )
    if settings.ai_provider == "gemini":
        if settings.gemini_api_key is None:
            return Unavailable(
                "provider-not-configured",
                "AI analysis is not configured: GEMINI_API_KEY is missing from server/.env.",
            )
        if settings.gemini_model is None:
            return Unavailable(
                "provider-not-configured",
                "AI analysis is not configured: GEMINI_MODEL is missing from server/.env.",
            )
    return None


def configured_model(settings: Settings) -> str | None:
    if settings.ai_provider == "gemini":
        return settings.gemini_model
    if settings.ai_provider == "scripted":
        from lexflow.analysis.scripted import MODEL

        return MODEL
    return None


def provider_for(settings: Settings) -> AnalysisProvider | Unavailable:
    missing = unavailable_reason(settings)
    if missing is not None:
        return missing
    if settings.ai_provider == "scripted":  # settings refuse it outside test/e2e databases
        from lexflow.analysis.scripted import ScriptedProvider

        return ScriptedProvider()
    key, model = settings.gemini_api_key, settings.gemini_model
    if key is None or model is None:  # pragma: no cover - unavailable_reason covers it
        return Unavailable("provider-not-configured", "AI analysis is not configured.")
    return GeminiProvider(key, model, timeout_seconds=settings.ai_timeout_seconds)
