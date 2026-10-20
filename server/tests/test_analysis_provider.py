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


def settings(**values: str) -> Settings:
    return Settings(**{"DATABASE_URL": TEST_DB, "LEXFLOW_ENV": "test", **values})  # type: ignore[arg-type]


def test_provider_for_reports_what_is_missing() -> None:
    off = provider_for(settings())
    assert isinstance(off, Unavailable) and off.code == "analysis-disabled"
    no_key = provider_for(settings(LEXFLOW_AI_PROVIDER="gemini", GEMINI_MODEL="m-1"))
    assert isinstance(no_key, Unavailable) and "GEMINI_API_KEY" in no_key.reason
    no_model = provider_for(settings(LEXFLOW_AI_PROVIDER="gemini", GEMINI_API_KEY=FAKE_KEY))
    assert isinstance(no_model, Unavailable) and "GEMINI_MODEL" in no_model.reason
    for missing in (off, no_key, no_model):
        assert FAKE_KEY not in missing.reason
    ready = provider_for(
        settings(LEXFLOW_AI_PROVIDER="gemini", GEMINI_API_KEY=FAKE_KEY, GEMINI_MODEL="m-1")
    )
    assert isinstance(ready, GeminiProvider) and isinstance(ready, AnalysisProvider)
    assert FAKE_KEY not in repr(ready)
    assert unavailable_reason(settings(LEXFLOW_AI_PROVIDER="scripted")) is None
    assert configured_model(settings(LEXFLOW_AI_PROVIDER="gemini", GEMINI_MODEL="m-1")) == "m-1"


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
