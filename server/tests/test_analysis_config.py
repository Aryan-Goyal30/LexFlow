"""AI analysis settings (Phase 5): off by default, the key stays secret, the
model has no default, and the scripted test double is fenced off."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lexflow.config import Settings

FAKE_KEY = "AIzaFAKE-test-key-0123456789-not-real"
TEST_DB = "postgresql+psycopg://u:p@127.0.0.1/lexflow_test"
LIVE_DB = "postgresql+psycopg://u:p@127.0.0.1/lexflow"
OUTSIDE_TESTS = {"LEXFLOW_PASSWORD_HASH_PROFILE": "standard", "LEXFLOW_AI_PROVIDER": "scripted"}


def settings(**values: str) -> Settings:
    base = {"DATABASE_URL": TEST_DB, "LEXFLOW_ENV": "test"}
    return Settings(**{**base, **values})  # type: ignore[arg-type]


def test_analysis_is_off_by_default() -> None:
    s = Settings(DATABASE_URL=LIVE_DB, GEMINI_API_KEY="", GEMINI_MODEL="")  # type: ignore[call-arg]
    assert s.ai_provider == "disabled"
    assert s.ai_allow_client_data is False
    assert s.gemini_api_key is None and s.gemini_model is None


def test_the_key_never_appears_in_repr_dump_or_json() -> None:
    s = settings(LEXFLOW_AI_PROVIDER="gemini", GEMINI_API_KEY=FAKE_KEY, GEMINI_MODEL="m-1")
    assert s.gemini_api_key is not None
    assert s.gemini_api_key.get_secret_value() == FAKE_KEY
    for shown in (repr(s), str(s), str(s.model_dump()), s.model_dump_json()):
        assert FAKE_KEY not in shown


def test_a_blank_key_counts_as_missing() -> None:
    assert settings(GEMINI_API_KEY="   ").gemini_api_key is None
    key = settings(GEMINI_API_KEY=f"  {FAKE_KEY}\n").gemini_api_key
    assert key is not None and key.get_secret_value() == FAKE_KEY


def test_model_name_has_no_default_and_is_checked() -> None:
    assert settings(LEXFLOW_AI_PROVIDER="gemini").gemini_model is None
    assert settings(GEMINI_MODEL=" models/some-model-1.0 ").gemini_model == "models/some-model-1.0"
    for bad in ("model name", "m;rm", "x" * 101, "../m?"):
        with pytest.raises(ValidationError):
            settings(GEMINI_MODEL=bad)


def test_the_scripted_double_is_refused_outside_test_and_e2e_databases() -> None:
    refused = "is a test double"
    with pytest.raises(ValidationError, match=refused):
        Settings(**{"DATABASE_URL": LIVE_DB, "LEXFLOW_ENV": "development", **OUTSIDE_TESTS})  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match=refused):
        Settings(**{"DATABASE_URL": TEST_DB, "LEXFLOW_ENV": "production", **OUTSIDE_TESTS})  # type: ignore[arg-type]
    e2e_db = "postgresql+psycopg://u:p@127.0.0.1/lexflow_e2e"
    e2e = Settings(**{"DATABASE_URL": e2e_db, "LEXFLOW_ENV": "development", **OUTSIDE_TESTS})  # type: ignore[arg-type]
    assert e2e.ai_provider == "scripted"


def test_limits_are_bounded() -> None:
    with pytest.raises(ValidationError):
        settings(LEXFLOW_AI_MAX_INPUT_CHARS="10")
    with pytest.raises(ValidationError):
        settings(LEXFLOW_AI_RUNS_PER_USER_PER_HOUR="0")
    s = settings(LEXFLOW_AI_TIMEOUT_SECONDS="90")
    assert s.ai_lease_seconds > 2 * s.ai_timeout_seconds
