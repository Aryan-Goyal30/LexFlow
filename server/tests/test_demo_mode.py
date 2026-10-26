"""The isolated demo database (Milestone 1): fictional clients and cases only
where the connected database is verified as the marked demo database.

Runs on the throwaway test database. The demo marker is written inside the
test's own transaction (rolled back afterwards), so no database keeps it.
"""

from __future__ import annotations

import importlib.util
import sys
import uuid
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from lexflow import demo
from lexflow.config import Settings, get_settings
from lexflow.models import AuditEvent, Case, Client, JudgmentSource, User
from lexflow.seed import sample_uuid
from tests.conftest import TEST_DATABASE_URL

As = Callable[[str], TestClient]
SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "e2e.py"
SAMPLE_CLIENT = sample_uuid("client", "c-005")


def settings(**values: Any) -> Settings:
    return Settings(**values)


@pytest.fixture
def demo_on(app: FastAPI) -> Iterator[Settings]:
    chosen = settings(LEXFLOW_DEMO_MODE=True, LEXFLOW_AI_PROVIDER="scripted")
    app.dependency_overrides[get_settings] = lambda: chosen
    yield chosen
    app.dependency_overrides.pop(get_settings, None)


def mark(db: Session) -> None:
    """Mark the test database as the demo one, inside the test transaction."""
    db.execute(text(demo.mark_statement(TEST_DATABASE_URL.database or "")))


def client_body(**extra: Any) -> dict[str, Any]:
    return {
        "name": "Velorindra Foods LLP (FICTIONAL)",
        "email": "contact@velorindra.example",
        "phone": "+91 00000 11111",
        **extra,
    }


def case_body(client_id: Any, lead: Any, **extra: Any) -> dict[str, Any]:
    return {
        "title": "Velorindra Foods LLP v. Tamsinwick Snacks Pvt. Ltd. (FICTIONAL)",
        "clientId": str(client_id),
        "practiceArea": "Intellectual Property",
        "status": "Open",
        "priority": "Medium",
        "leadAdvocateId": str(lead),
        "description": "FICTIONAL demo matter: trade mark KESORA, prior use and passing off.",
        **extra,
    }


# --- settings and the identity check ---------------------------------------------------


def test_demo_mode_is_off_by_default_and_refused_outside_a_test_or_e2e_database() -> None:
    assert settings().demo_mode is False
    with pytest.raises(ValueError, match="isolated demo database only"):
        settings(
            LEXFLOW_DEMO_MODE=True,
            DATABASE_URL="postgresql+psycopg://user@127.0.0.1:5432/lexflow",
        )
    with pytest.raises(ValueError, match="isolated demo database only"):
        settings(
            LEXFLOW_DEMO_MODE=True,
            DATABASE_URL="postgresql+psycopg://user@127.0.0.1:5432/lexflow_e2e?dbname=lexflow",
        )


def test_the_connected_database_must_carry_the_marker(db: Session) -> None:
    on = settings(LEXFLOW_DEMO_MODE=True)
    assert demo.status(db, settings()) == demo.DemoStatus(False, False, demo.OFF)
    unmarked = demo.status(db, on)
    assert (unmarked.enabled, unmarked.verified) == (True, False)
    mark(db)
    assert demo.status(db, on) == demo.DemoStatus(True, True, None)


def test_a_marked_database_other_than_the_configured_one_is_not_verified(db: Session) -> None:
    mark(db)
    elsewhere = TEST_DATABASE_URL.set(database="lexflow_other_test")
    other = settings(
        LEXFLOW_DEMO_MODE=True, DATABASE_URL=elsewhere.render_as_string(hide_password=False)
    )
    assert demo.status(db, other).verified is False


def test_only_a_test_or_e2e_database_can_be_marked() -> None:
    for name in ("lexflow", "lexflow_latest", 'lexflow_e2e" ; DROP', ""):
        with pytest.raises(ValueError):
            demo.mark_statement(name)
    assert demo.mark_statement("lexflow_e2e").endswith(f"'{demo.DEMO_MARKER}'")


# --- the API: fictional records only in the verified demo database ---------------------


def test_without_a_verified_demo_database_nothing_fictional_is_written(
    as_: As, db: Session, demo_on: Settings, people: dict[str, User]
) -> None:
    lead = as_("lead")
    assert lead.get("/api/demo").json() == {
        "enabled": True,
        "verified": False,
        "reason": demo.UNVERIFIED,
    }
    clients_before = db.scalar(select(func.count()).select_from(Client))
    refused = lead.post("/api/clients", json=client_body(fictional=True))
    assert (refused.status_code, refused.json()["code"]) == (409, "demo-environment-unverified")
    refused = lead.post(
        "/api/cases", json=case_body(SAMPLE_CLIENT, people["lead"].id, fictional=True)
    )
    assert (refused.status_code, refused.json()["code"]) == (409, "demo-environment-unverified")
    assert db.scalar(select(func.count()).select_from(Client)) == clients_before


def test_with_demo_mode_off_fictional_records_are_refused(
    as_: As, db: Session, people: dict[str, User]
) -> None:
    mark(db)  # even a marked database does not help while demo mode is off
    lead = as_("lead")
    assert lead.get("/api/demo").json()["enabled"] is False
    refused = lead.post("/api/clients", json=client_body(fictional=True))
    assert refused.status_code == 409


def test_in_the_verified_demo_database_a_fictional_case_can_be_analysed(
    as_: As, db: Session, demo_on: Settings, people: dict[str, User]
) -> None:
    mark(db)
    lead = as_("lead")
    assert lead.get("/api/demo").json() == {"enabled": True, "verified": True, "reason": None}
    created = lead.post("/api/clients", json=client_body(fictional=True))
    assert created.status_code == 201 and created.json()["isSample"] is True
    client_id = created.json()["id"]
    opened = lead.post("/api/cases", json=case_body(client_id, people["lead"].id, fictional=True))
    assert opened.status_code == 201, opened.text
    case = opened.json()
    assert case["isSample"] is True
    setup = lead.get(f"/api/cases/{case['id']}/analysis/setup").json()
    assert setup["caseIsSample"] is True and setup["sampleOnly"] is True
    assert (setup["canRun"], setup["cannotRunReason"]) == (True, None)  # D1 is unchanged
    (event,) = db.scalars(select(AuditEvent).where(AuditEvent.action == "case.created"))
    assert event.details == {"caseNumber": case["caseNumber"], "fictional": True}


def test_a_fictional_case_needs_a_fictional_client(
    as_: As, db: Session, demo_on: Settings, people: dict[str, User]
) -> None:
    mark(db)
    lead = as_("lead")
    real = lead.post("/api/clients", json=client_body(name="Ordinary Client"))
    assert real.status_code == 201 and real.json()["isSample"] is False
    refused = lead.post(
        "/api/cases", json=case_body(real.json()["id"], people["lead"].id, fictional=True)
    )
    assert refused.status_code == 422
    assert refused.json()["errors"][0]["field"] == "clientId"


def test_an_ordinary_case_stays_ordinary_in_demo_mode(
    as_: As, db: Session, demo_on: Settings, people: dict[str, User]
) -> None:
    mark(db)
    lead = as_("lead")
    opened = lead.post("/api/cases", json=case_body(SAMPLE_CLIENT, people["lead"].id))
    assert opened.status_code == 201 and opened.json()["isSample"] is False
    found = db.get(Case, uuid.UUID(opened.json()["id"]))
    assert found is not None and found.is_sample is False


# --- the demo database's destructive setup fails closed ---------------------------------


def load_e2e_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("e2e_script", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_the_demo_setup_refuses_the_live_database_before_connecting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_e2e_script()
    monkeypatch.setenv("LEXFLOW_E2E_DATABASE", "lexflow")
    with pytest.raises(SystemExit, match="'e2e' must be a part"):
        script.e2e_database_url()
    # A DATABASE_URL that itself names the e2e database is the app's own database.
    live_named_e2e = TEST_DATABASE_URL.set(database="lexflow_e2e")
    monkeypatch.setenv("DATABASE_URL", live_named_e2e.render_as_string(hide_password=False))
    monkeypatch.delenv("LEXFLOW_E2E_DATABASE")
    with pytest.raises(SystemExit, match="it is the DATABASE_URL database"):
        script.e2e_database_url()


def test_the_demo_setup_refuses_an_unmarked_database(engine: Engine) -> None:
    script = load_e2e_script()
    with pytest.raises(SystemExit, match="not the freshly created, marked demo database"):
        script.verify_identity(engine, TEST_DATABASE_URL.database or "")


def test_the_setup_never_resets_a_database_that_holds_genuine_judgments(
    committed_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = load_e2e_script()
    missing = TEST_DATABASE_URL.set(database="lexflow_absent_e2e_test")
    assert script.holds_genuine_judgments(missing) is False
    assert script.holds_genuine_judgments(TEST_DATABASE_URL) is False
    with Session(committed_engine) as session:
        session.add(
            JudgmentSource(
                key="test-unflagged-source",
                name="TEST ONLY: unflagged source (not real law)",
                terms_url="https://terms.example.org/test-only",
                terms_checked_on=date(2026, 10, 25),
                terms_checked_by="LexFlow tests",
                permitted_use="Test only.",
                is_synthetic=False,
            )
        )
        session.commit()
    assert script.holds_genuine_judgments(TEST_DATABASE_URL) is True
    monkeypatch.setattr(script, "e2e_database_url", lambda: TEST_DATABASE_URL)
    with pytest.raises(SystemExit, match="holds genuine"):
        script.prepare()
    # Nothing was dropped: the row is still there.
    with Session(committed_engine) as session:
        assert session.scalar(select(func.count()).select_from(JudgmentSource)) == 1


def test_the_accounts_command_refuses_a_short_password_before_connecting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_e2e_script()
    monkeypatch.setenv("LEXFLOW_E2E_PASSWORD", "short")

    def never() -> None:
        raise AssertionError("nothing may connect before the password is checked")

    monkeypatch.setattr(script, "e2e_database_url", never)
    with pytest.raises(SystemExit, match="at least 12 characters"):
        script.accounts()


def test_the_accounts_command_refuses_an_unmarked_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_e2e_script()
    monkeypatch.setenv("LEXFLOW_E2E_PASSWORD", "a-long-test-password")
    monkeypatch.setattr(script, "e2e_database_url", lambda: TEST_DATABASE_URL)
    with pytest.raises(SystemExit, match="not the freshly created, marked demo database"):
        script.accounts()


def test_the_accounts_command_sets_the_password_without_resetting_anything(
    committed_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lexflow.auth import passwords

    script = load_e2e_script()
    with Session(committed_engine) as session:
        session.add(User(name="E2E Admin (test)", email="e2e.admin@lexflow.test",
                         role="Administrator"))  # fmt: skip
        session.commit()
    monkeypatch.setenv("LEXFLOW_E2E_PASSWORD", "a-long-test-password")
    monkeypatch.setattr(script, "e2e_database_url", lambda: TEST_DATABASE_URL)
    monkeypatch.setattr(script, "verify_identity", lambda engine, name: None)
    monkeypatch.setattr(script, "E2E_ACCOUNTS", [("e2e.admin@lexflow.test", "x", "Administrator")])
    assert script.accounts() == 0
    with Session(committed_engine) as session:
        user = session.scalars(select(User)).one()
        profile = Settings().password_hash_profile
        assert user.password_hash and passwords.verify_password(
            user.password_hash, "a-long-test-password", profile
        )
