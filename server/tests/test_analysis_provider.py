"""The provider layer (Phase 5 M3). No test contacts Google: the Gemini SDK
client is replaced by a fake, and building a real one fails (conftest)."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
import pytest
from google import genai
from google.genai import errors
from pydantic import SecretStr

from lexflow.analysis import prompt
from lexflow.analysis.output import RESPONSE_SCHEMA, parse
from lexflow.analysis.provider import (
    AnalysisProvider,
    GeminiProvider,
    ProviderError,
    Request,
    Unavailable,
    configured_model,
    provider_for,
    unavailable_reason,
)
from lexflow.analysis.scripted import ScriptedProvider
from lexflow.config import Settings
from tests.analysis_fakes import Factory, FakeGeminiClient, evidence, response

FAKE_KEY = "AIzaFAKE-test-key-0123456789-not-real"
TEST_DB = "postgresql+psycopg://u:p@127.0.0.1/lexflow_test"


def request() -> Request:
    ev = evidence()
    return Request(
        system_instruction=prompt.SYSTEM_INSTRUCTION,
        prompt=prompt.render(ev),
        response_schema=RESPONSE_SCHEMA,
        max_output_tokens=4096,
        evidence=ev,
    )


def gemini(*script: Any) -> tuple[GeminiProvider, Factory]:
    factory = Factory(FakeGeminiClient(list(script)))
    provider = GeminiProvider(
        SecretStr(FAKE_KEY), "test-model-1", timeout_seconds=45, client_factory=factory
    )
    return provider, factory


def test_a_request_carries_the_schema_instructions_and_limits() -> None:
    provider, factory = gemini(response('{"facts": []}'))
    answer = provider.generate(request())
    assert answer.text == '{"facts": []}' and not answer.truncated
    assert factory.built == [(FAKE_KEY, 45_000)]  # the timeout is in milliseconds
    call = factory.client.calls[0]
    assert call["model"] == "test-model-1"
    assert call["contents"] == request().prompt
    config = call["config"]
    assert config.system_instruction == prompt.SYSTEM_INSTRUCTION
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == RESPONSE_SCHEMA
    assert config.max_output_tokens == 4096
    assert config.candidate_count == 1
    assert answer.usage == {
        "promptTokens": 1200,
        "outputTokens": 300,
        "thinkingTokens": 50,
        "totalTokens": 1550,
    }


def test_thought_parts_are_not_part_of_the_answer() -> None:
    provider, _ = gemini(response('{"facts": []}', thought="private reasoning"))
    assert provider.generate(request()).text == '{"facts": []}'


def test_an_answer_cut_off_at_the_token_limit_is_marked() -> None:
    provider, _ = gemini(response('{"facts": [', finish="MAX_TOKENS"))
    assert provider.generate(request()).truncated


@pytest.mark.parametrize(
    ("failure", "code", "retry"),
    [
        (
            errors.ClientError(429, {"error": {"message": f"PROVIDER-ECHO {FAKE_KEY}"}}),
            "provider-rate-limited",
            True,
        ),
        (errors.ClientError(400, {"error": {"message": "bad"}}), "provider-rejected", False),
        (errors.ClientError(401, {"error": {"message": "no"}}), "provider-auth-failed", False),
        (errors.ClientError(403, {"error": {"message": "no"}}), "provider-auth-failed", False),
        (
            errors.ClientError(404, {"error": {"message": "no model"}}),
            "provider-model-not-found",
            False,
        ),
        (errors.ServerError(500, {"error": {"message": "oops"}}), "provider-unavailable", True),
        (errors.ServerError(503, {"error": {"message": "busy"}}), "provider-unavailable", True),
        (httpx.ReadTimeout(f"timed out {FAKE_KEY}"), "provider-timeout", True),
        (httpx.ConnectError("no route"), "provider-unreachable", True),
        (TimeoutError(), "provider-timeout", True),
    ],
)
def test_failures_map_to_fixed_codes_and_messages(
    failure: BaseException, code: str, retry: bool, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    provider, _ = gemini(failure)
    with pytest.raises(ProviderError) as caught:
        provider.generate(request())
    assert (caught.value.code, caught.value.retry) == (code, retry)
    # The provider's own text (which could echo anything) is never passed on.
    assert FAKE_KEY not in caught.value.message and "PROVIDER-ECHO" not in caught.value.message
    assert caught.value.__cause__ is None and caught.value.__suppress_context__
    assert FAKE_KEY not in caplog.text


ERROR_INFO = "type.googleapis.com/google.rpc.ErrorInfo"
ECHO = f"PROVIDER-ECHO {FAKE_KEY} DOCUMENT-TEXT registered trade mark SATTVIK"


def google_error(
    status: Any = "INVALID_ARGUMENT", details: Any = None, **extra: Any
) -> dict[str, Any]:
    """The body Google's APIs send (google.rpc.Status), with free text that echoes
    the key and document text, as a hostile or careless provider message might."""
    if details is None:
        details = [
            {
                "@type": ERROR_INFO,
                "reason": "API_KEY_INVALID",
                "domain": "googleapis.com",
                "metadata": {"note": ECHO},
            },
            {"@type": "type.googleapis.com/google.rpc.LocalizedMessage", "message": ECHO},
        ]
    return {"error": {"code": 400, "message": ECHO, "status": status, "details": details, **extra}}


def captured(failure: BaseException) -> ProviderError:
    provider, _ = gemini(failure)
    with pytest.raises(ProviderError) as caught:
        provider.generate(request())
    return caught.value


def test_google_status_and_reason_are_captured_from_structured_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    error = captured(errors.ClientError(400, google_error()))
    assert error.diagnostic == {
        "httpStatus": "400",
        "status": "INVALID_ARGUMENT",
        "reason": "API_KEY_INVALID",
    }
    # The user-facing message stays generic and unchanged.
    assert (error.code, error.message, error.retry) == (
        "provider-rejected",
        "Google's API refused the request (400).",
        False,
    )
    # The codes stay out of the message, the exception text and the log; and no
    # provider free text, key or document text reaches any of them or the diagnostic.
    shown = [error.message, str(error), repr(error.args), caplog.text]
    for text in shown:
        assert "INVALID_ARGUMENT" not in text and "API_KEY_INVALID" not in text
    everything = [*shown, repr(error.diagnostic)]
    for secret in (FAKE_KEY, "PROVIDER-ECHO", "DOCUMENT-TEXT", "SATTVIK"):
        assert all(secret not in text for text in everything)


def test_status_alone_is_enough_and_a_server_error_keeps_its_retry() -> None:
    only_status = captured(errors.ClientError(400, {"error": {"status": "INVALID_ARGUMENT"}}))
    assert only_status.diagnostic == {"httpStatus": "400", "status": "INVALID_ARGUMENT"}
    busy = captured(errors.ServerError(503, {"error": {"status": "UNAVAILABLE", "message": "x"}}))
    assert (busy.code, busy.retry) == ("provider-unavailable", True)
    assert busy.diagnostic == {"httpStatus": "503", "status": "UNAVAILABLE"}


def info(reason: Any, **extra: Any) -> dict[str, Any]:
    return {"@type": ERROR_INFO, "reason": reason, **extra}


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        # Status values that are not google.rpc.Code names.
        (google_error(status="invalid_argument", details=[]), {}),
        (google_error(status="INVALID ARGUMENT", details=[]), {}),
        (google_error(status="INVALID_ARGUMENT\nINJECTED", details=[]), {}),
        (google_error(status=" INVALID_ARGUMENT", details=[]), {}),
        (google_error(status="A" * 41, details=[]), {}),
        (google_error(status=FAKE_KEY, details=[]), {}),
        (google_error(status=400, details=[]), {}),
        (google_error(status=None, details=[]), {}),
        # The SDK's own stand-in when the body was not JSON (an HTTP reason phrase).
        ({"message": ECHO, "status": "Bad Request"}, {}),
        # Reasons that are not UPPER_SNAKE_CASE codes, or are too long.
        (google_error(details=[info("api_key_invalid")]), {}),
        (google_error(details=[info("API-KEY-INVALID")]), {}),
        (google_error(details=[info("A")]), {}),
        (google_error(details=[info("A" * 64)]), {}),
        (google_error(details=[info(FAKE_KEY)]), {}),
        (google_error(details=[info("API_KEY_INVALID ")]), {}),
        (google_error(details=[info("API_KEY_INVALID\n")]), {}),
        (google_error(details=[info(["API_KEY_INVALID"])]), {}),
        (google_error(details=[info(None)]), {}),
        # A reason is only read from a google.rpc.ErrorInfo entry.
        (google_error(details=[{"@type": "type.googleapis.com/other", "reason": "SNEAKY"}]), {}),
        (google_error(details=[{"reason": "SNEAKY"}]), {}),
        (google_error(details=[{"@type": ERROR_INFO}]), {}),
        # Unexpected shapes are ignored, not trusted and not raised.
        (google_error(details="API_KEY_INVALID"), {}),
        (google_error(details={"reason": "API_KEY_INVALID"}), {}),
        (google_error(details=["API_KEY_INVALID", 7, None]), {}),
        ({"error": "API_KEY_INVALID"}, {}),
        (
            {"error": {"status": "INVALID_ARGUMENT", "details": None}},
            {"status": "INVALID_ARGUMENT"},
        ),
        (ECHO, {}),
        # Boundaries and recovery: 63 characters is the longest reason, and a later
        # valid ErrorInfo is used when an earlier one is not.
        (google_error(details=[info("A" * 63)]), {"reason": "A" * 63}),
        (
            google_error(details=[info("bad reason"), info("GOOD_REASON")]),
            {"reason": "GOOD_REASON"},
        ),
    ],
)
def test_malformed_or_unexpected_values_are_discarded(
    body: Any, expected: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    error = captured(errors.ClientError(400, body))
    status_given = isinstance(body, dict) and isinstance(body.get("error"), dict)
    valid_status = status_given and body["error"].get("status") == "INVALID_ARGUMENT"
    want = {"httpStatus": "400", **expected}
    if valid_status and "status" not in want:
        want["status"] = "INVALID_ARGUMENT"
    assert error.diagnostic == want
    assert (error.code, error.message) == (
        "provider-rejected",
        "Google's API refused the request (400).",
    )
    for secret in (FAKE_KEY, "PROVIDER-ECHO", "DOCUMENT-TEXT", "SATTVIK", "INJECTED"):
        assert all(secret not in text for text in (error.message, str(error), caplog.text))
        assert secret not in repr(error.diagnostic)


def test_failures_without_a_google_error_carry_no_provider_codes() -> None:
    for failure in (
        httpx.ReadTimeout(f"timed out {FAKE_KEY}"),
        httpx.ConnectError("no route"),
        TimeoutError(),
    ):
        assert captured(failure).diagnostic == {}
    assert ProviderError("provider-empty", "x").diagnostic == {}


@pytest.mark.parametrize(
    ("answer", "code"),
    [
        (response("{}", block="SAFETY"), "provider-blocked"),
        (response("{}", finish="SAFETY"), "provider-blocked"),
        (response("{}", finish="PROHIBITED_CONTENT"), "provider-blocked"),
        (response("{}", candidates=[]), "provider-empty"),
        (response("   "), "provider-empty"),
    ],
)
def test_blocked_and_empty_answers_fail(answer: Any, code: str) -> None:
    provider, _ = gemini(answer)
    with pytest.raises(ProviderError) as caught:
        provider.generate(request())
    assert caught.value.code == code and not caught.value.retry


def test_the_default_client_uses_the_key_and_no_sdk_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    built: list[dict[str, Any]] = []

    class Recorder:
        def __init__(self, **kwargs: Any) -> None:
            built.append(kwargs)
            self.models = FakeGeminiClient([response('{"facts": []}')])

    monkeypatch.setattr(genai, "Client", Recorder)
    GeminiProvider(SecretStr(FAKE_KEY), "m", timeout_seconds=30).generate(request())
    (kwargs,) = built
    assert kwargs["api_key"] == FAKE_KEY
    assert kwargs["http_options"].timeout == 30_000
    assert kwargs["http_options"].retry_options is None


def test_the_conftest_guard_refuses_a_real_client() -> None:
    with pytest.raises(AssertionError, match="real Gemini client"):
        GeminiProvider(SecretStr(FAKE_KEY), "m", timeout_seconds=30).generate(request())


# Words that belong to operators, never to messages shown to advocates or clients.
OPERATOR_WORDS = ("GEMINI", "LEXFLOW_", ".env", "API_KEY", "server/")


def settings(**values: str) -> Settings:
    return Settings(**{"DATABASE_URL": TEST_DB, "LEXFLOW_ENV": "test", **values})  # type: ignore[arg-type]


def test_provider_for_reports_what_is_missing() -> None:
    off = provider_for(settings())
    assert isinstance(off, Unavailable) and off.code == "analysis-disabled"
    no_key = provider_for(settings(LEXFLOW_AI_PROVIDER="gemini", GEMINI_MODEL="m-1"))
    assert isinstance(no_key, Unavailable) and no_key.code == "provider-not-configured"
    assert no_key.detail is not None and "GEMINI_API_KEY" in no_key.detail
    no_model = provider_for(settings(LEXFLOW_AI_PROVIDER="gemini", GEMINI_API_KEY=FAKE_KEY))
    assert isinstance(no_model, Unavailable) and no_model.detail is not None
    assert "GEMINI_MODEL" in no_model.detail
    for missing in (off, no_key, no_model):
        # The reason is shown to every staff member: no setting, file or key names.
        assert missing.reason and FAKE_KEY not in f"{missing.reason} {missing.detail}"
        assert not any(word in missing.reason for word in OPERATOR_WORDS)
    ready = provider_for(
        settings(LEXFLOW_AI_PROVIDER="gemini", GEMINI_API_KEY=FAKE_KEY, GEMINI_MODEL="m-1")
    )
    assert isinstance(ready, GeminiProvider) and isinstance(ready, AnalysisProvider)
    assert FAKE_KEY not in repr(ready)
    assert unavailable_reason(settings(LEXFLOW_AI_PROVIDER="scripted")) is None
    assert configured_model(settings(LEXFLOW_AI_PROVIDER="gemini", GEMINI_MODEL="m-1")) == "m-1"


@pytest.mark.parametrize("name", ["local", "openai", "Gemini", "", "gemini "])
def test_an_unknown_provider_fails_closed_and_never_reaches_gemini(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The settings only accept known names, but a value that slips past them
    (here forced with model_copy, which skips validation) must not fall through
    to Gemini, even with a key and a model configured."""
    built: list[Any] = []
    monkeypatch.setattr(GeminiProvider, "__init__", lambda *a, **k: built.append(a))
    forced = settings(
        LEXFLOW_AI_PROVIDER="gemini", GEMINI_API_KEY=FAKE_KEY, GEMINI_MODEL="m-1"
    ).model_copy(update={"ai_provider": name})
    refused = provider_for(forced)
    assert isinstance(refused, Unavailable) and refused.code == "provider-unsupported"
    assert unavailable_reason(forced) == refused
    assert configured_model(forced) is None
    assert built == []
    assert not any(word in refused.reason for word in OPERATOR_WORDS)
    assert refused.detail is not None and "LEXFLOW_AI_PROVIDER" in refused.detail
    assert FAKE_KEY not in f"{refused.reason} {refused.detail}"


def test_the_disabled_and_scripted_providers_keep_their_behaviour() -> None:
    off = unavailable_reason(settings(LEXFLOW_AI_PROVIDER="disabled"))
    assert off is not None and off.code == "analysis-disabled"
    assert off.reason == "AI analysis is turned off on this server."
    assert isinstance(provider_for(settings(LEXFLOW_AI_PROVIDER="scripted")), ScriptedProvider)


QUOTA_FAILURE = "type.googleapis.com/google.rpc.QuotaFailure"


def quota_error(*quota_ids: Any, status: int = 429) -> errors.ClientError:
    return errors.ClientError(
        status,
        {
            "error": {
                "code": status,
                "message": ECHO,
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "@type": QUOTA_FAILURE,
                        "violations": [
                            {"quotaMetric": ECHO, "quotaId": q, "quotaValue": "50"}
                            for q in quota_ids
                        ],
                    }
                ],
            }
        },
    )


@pytest.mark.parametrize(
    ("quota_id", "code", "retry"),
    [
        ("GenerateRequestsPerDayPerProjectPerModel-FreeTier", "provider-quota-exhausted", False),
        ("GenerateContentDailyInputTokens", "provider-quota-exhausted", False),
        ("RequestsPerMonthPerProject", "provider-quota-exhausted", False),
        ("GenerateRequestsPerMinutePerProjectPerModel-FreeTier", "provider-rate-limited", True),
        ("GenerateContentInputTokensPerModelPerMinute", "provider-rate-limited", True),
    ],
)
def test_an_exhausted_daily_quota_is_not_retried_but_a_rate_limit_is(
    quota_id: str, code: str, retry: bool, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    error = captured(quota_error(quota_id))
    assert (error.code, error.retry) == (code, retry)
    assert error.diagnostic == {
        "httpStatus": "429",
        "status": "RESOURCE_EXHAUSTED",
        "quotaId": quota_id,
    }
    assert quota_id not in error.message and "(429)" in error.message
    assert not any(word in error.message for word in OPERATOR_WORDS)
    for secret in (FAKE_KEY, "PROVIDER-ECHO", "SATTVIK"):
        assert all(secret not in t for t in (error.message, repr(error.diagnostic), caplog.text))


def test_quota_classification_reads_only_valid_structured_fields() -> None:
    # No QuotaFailure at all: an ordinary 429 keeps its retries.
    plain = captured(errors.ClientError(429, {"error": {"message": "PerDay quota PerDay"}}))
    assert (plain.code, plain.retry) == ("provider-rate-limited", True)
    # "PerDay" only in free text or in an invalid id does not count.
    for odd in ("Per Day quota", "PerDay<script>", "x" * 101, 7, None):
        error = captured(quota_error(odd))
        assert (error.code, error.retry) == ("provider-rate-limited", True), odd
        assert "quotaId" not in error.diagnostic
    # The same id inside another detail type is ignored.
    other = errors.ClientError(
        429,
        {
            "error": {
                "details": [
                    {"@type": ERROR_INFO, "violations": [{"quotaId": "RequestsPerDay"}]},
                ]
            }
        },
    )
    assert captured(other).code == "provider-rate-limited"
    # A long quota named on a non-429 answer does not change that answer's meaning.
    assert captured(quota_error("RequestsPerDay", status=403)).code == "provider-auth-failed"
    # With several violations, any daily one makes the quota exhausted.
    both = captured(quota_error("RequestsPerMinute", "RequestsPerDay"))
    assert (both.code, both.retry) == ("provider-quota-exhausted", False)
    assert both.diagnostic["quotaId"] == "RequestsPerMinute"


@pytest.mark.parametrize(
    "failure",
    [
        errors.ClientError(401, {"error": {"message": "no"}}),
        errors.ClientError(403, {"error": {"message": "no"}}),
        errors.ClientError(404, {"error": {"message": "no"}}),
        errors.ClientError(400, {"error": {"message": "no"}}),
        errors.ClientError(429, {"error": {"message": "no"}}),
        quota_error("RequestsPerDay"),
        errors.ServerError(503, {"error": {"message": "no"}}),
        httpx.ReadTimeout("t"),
        httpx.ConnectError("c"),
    ],
)
def test_provider_messages_are_safe_for_every_staff_member(failure: BaseException) -> None:
    message = captured(failure).message
    assert message and not any(word in message for word in OPERATOR_WORDS)
    assert "ECHO" not in message


def test_the_scripted_double_quotes_its_evidence_and_cites_one_unknown_passage() -> None:
    scripted = provider_for(settings(LEXFLOW_AI_PROVIDER="scripted"))
    assert isinstance(scripted, ScriptedProvider) and scripted.model == "scripted-v1"
    answer = scripted.generate(request())
    data = json.loads(answer.text)
    assert all(f["statement"].startswith("[Scripted]") for f in data["facts"])
    assert [f["evidence"] for f in data["facts"]] == ["D1", "D2", "D999"]
    assert data["precedents"][0]["evidence"] == "J1"
    parsed = parse(answer.text)
    assert parsed.malformed == 0 and not parsed.insufficient_evidence
    empty = scripted.generate(
        Request("s", "p", RESPONSE_SCHEMA, 100, evidence(passages=False, judgments=False))
    )
    assert json.loads(empty.text)["insufficient_evidence"] is True
