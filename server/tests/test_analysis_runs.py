"""Analysis runs end to end (Phase 5 M5): API access rules, the worker step,
retries, audit and key secrecy. No test contacts Google: the provider is the
scripted double or a fake with prepared answers. Synthetic text only."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from lexflow import worker
from lexflow.analysis import runs
from lexflow.analysis.provider import ProviderError, Response
from lexflow.analysis.scripted import ScriptedProvider
from lexflow.config import Settings, get_settings
from lexflow.models import AnalysisRun, AuditEvent, Case, Document
from lexflow.seed import sample_uuid
from tests.access_fixtures import SATTVIK
from tests.analysis_fakes import ScriptedAnswers
from tests.conftest import APP_HEADERS, shared_sessions, sign_in
from tests.embedding_fakes import make_ready
from tests.test_portal import as_client, portal_people  # noqa: F401 - fixtures

As = Callable[[str], TestClient]
OTHER_CASE = sample_uuid("case", "case-1001")
FAKE_KEY = "AIzaFAKE-test-key-0123456789-not-real"
TEXT = (
    "SYNTHETIC. The plaintiff's registered trade mark SATTVIK was first used on packaged "
    "snack foods in 2015. The defendant adopted a similar mark in 2024."
)
REPLY = (
    "SYNTHETIC. The defendant says its mark was adopted honestly in 2023 and denies passing off."
)


def ai(**values: Any) -> Settings:
    return Settings(**{"LEXFLOW_AI_PROVIDER": "scripted", **values})


@pytest.fixture
def configure(app: FastAPI) -> Iterator[Callable[..., Settings]]:
    def use(**values: Any) -> Settings:
        chosen = ai(**values)
        app.dependency_overrides[get_settings] = lambda: chosen
        return chosen

    yield use
    app.dependency_overrides.pop(get_settings, None)


@pytest.fixture
def docs(db: Session, people: Any) -> list[uuid.UUID]:
    return [
        make_ready(db, SATTVIK, "Notice.pdf", [TEXT]),
        make_ready(db, SATTVIK, "Reply.pdf", [REPLY]),
    ]


def runs_url(case_id: Any = SATTVIK) -> str:
    return f"/api/cases/{case_id}/analysis-runs"


def start(http: TestClient, document_ids: list[uuid.UUID], **extra: Any) -> Any:
    body = {"documentIds": [str(d) for d in document_ids], "confirmTransmission": True, **extra}
    return http.post(runs_url(), json=body)


def work(db: Session, provider: Any, settings: Settings, worker_id: str = "w1") -> bool:
    return worker.run_next_analysis(
        shared_sessions(db), provider, settings, worker_id, lambda: datetime.now(UTC)
    )


def events(db: Session, action: str) -> list[AuditEvent]:
    return list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.action == action)
            .order_by(AuditEvent.occurred_at, AuditEvent.id)
        )
    )


# --- setup and access -----------------------------------------------------------------


def test_setup_says_when_analysis_is_off(as_: As, docs: list[uuid.UUID]) -> None:
    body = as_("lead").get(f"/api/cases/{SATTVIK}/analysis/setup").json()
    assert body["available"] is False and "turned off" in body["unavailableReason"]
    assert body["canRun"] is False and body["provider"] is None
    assert {d["name"]: d["eligible"] for d in body["documents"]}["Notice.pdf"] is True
    assert body["promptVersion"] == "case-analysis-v1"


def test_setup_with_a_configured_provider(
    as_: As, docs: list[uuid.UUID], configure: Callable[..., Settings]
) -> None:
    configure()
    lead = as_("lead").get(f"/api/cases/{SATTVIK}/analysis/setup").json()
    assert lead["available"] and lead["canRun"] and lead["caseIsSample"] and lead["sampleOnly"]
    assert lead["providerLabel"] == "Scripted test provider (not AI)"
    assert lead["model"] == "scripted-v1" and lead["judgmentsAvailable"] == 0
    for role in ("admin", "associate"):
        assert as_(role).get(f"/api/cases/{SATTVIK}/analysis/setup").json()["canRun"]
    paralegal = as_("paralegal").get(f"/api/cases/{SATTVIK}/analysis/setup").json()
    assert paralegal["canRun"] is False and "advocates" in paralegal["cannotRunReason"]


def test_case_permissions_say_who_may_run_an_analysis(as_: As) -> None:
    allowed = {
        role: as_(role).get(f"/api/cases/{SATTVIK}").json()["permissions"]["canRunAnalysis"]
        for role in ("admin", "lead", "associate", "paralegal")
    }
    assert allowed == {"admin": True, "lead": True, "associate": True, "paralegal": False}


@pytest.mark.parametrize("role", ["other_advocate", "other_paralegal"])
def test_outsiders_learn_nothing_about_a_case_or_its_runs(
    role: str, as_: As, db: Session, docs: list[uuid.UUID], configure: Callable[..., Settings]
) -> None:
    configure()
    run_id = start(as_("lead"), docs).json()["id"]
    http = as_(role)
    missing = str(uuid.uuid4())
    for path in (
        "/api/cases/{}/analysis/setup",
        "/api/cases/{}/analysis-runs",
        "/api/cases/{}/analysis-runs/" + run_id,
    ):
        hidden = http.get(path.format(SATTVIK))
        absent = http.get(path.format(missing))
        assert hidden.status_code == absent.status_code == 404
        assert hidden.json() == absent.json()
    refused = start(http, docs)
    assert refused.status_code == 404 and refused.json()["code"] == "case-not-found"


def test_clients_and_anonymous_callers_never_reach_analysis(
    as_client: As,  # noqa: F811 - the fixture imported from test_portal
    anon_client: TestClient,
    docs: list[uuid.UUID],
) -> None:
    assert as_client("client").get(runs_url()).status_code == 403
    assert as_client("client").post(runs_url(), json={}).status_code == 403
    assert anon_client.get(runs_url()).status_code == 401


def test_paralegals_may_read_but_not_start(
    as_: As, docs: list[uuid.UUID], configure: Callable[..., Settings]
) -> None:
    configure()
    refused = start(as_("paralegal"), docs)
    assert refused.status_code == 403
    assert as_("paralegal").get(runs_url()).status_code == 200


def test_archived_cases_are_refused_but_their_runs_stay_readable(
    as_: As, db: Session, docs: list[uuid.UUID], configure: Callable[..., Settings]
) -> None:
    configure()
    run_id = start(as_("lead"), docs).json()["id"]
    case = db.get(Case, SATTVIK)
    assert case is not None
    case.archived_at = datetime.now(UTC)
    db.commit()
    refused = start(as_("admin"), docs)
    assert refused.status_code == 409 and refused.json()["code"] == "case-archived"
    assert as_("lead").get(f"{runs_url()}/{run_id}").status_code == 200


# --- starting a run -------------------------------------------------------------------


def test_a_run_needs_configuration(
    as_: As, docs: list[uuid.UUID], configure: Callable[..., Settings]
) -> None:
    off = start(as_("lead"), docs)
    assert off.status_code == 503 and off.json()["code"] == "analysis-unavailable"
    configure(LEXFLOW_AI_PROVIDER="gemini", GEMINI_MODEL="m-1")
    no_key = start(as_("lead"), docs)
    assert no_key.status_code == 503 and "GEMINI_API_KEY" in no_key.json()["detail"]


def test_a_run_needs_explicit_confirmation_and_valid_input(
    as_: As, docs: list[uuid.UUID], configure: Callable[..., Settings]
) -> None:
    configure()
    unconfirmed = start(as_("lead"), docs, confirmTransmission=False)
    assert unconfirmed.status_code == 422 and unconfirmed.json()["code"] == "confirmation-required"
    for body in (
        {"documentIds": [], "confirmTransmission": True},
        {"documentIds": [str(docs[0])], "confirmTransmission": True, "prompt": "do x"},
        {"documentIds": ["not-a-uuid"], "confirmTransmission": True},
        {"documentIds": [str(uuid.uuid4())] * 101, "confirmTransmission": True},
    ):
        assert as_("lead").post(runs_url(), json=body).status_code == 422


def test_only_ready_live_documents_of_this_case_may_be_selected(
    as_: As, db: Session, docs: list[uuid.UUID], configure: Callable[..., Settings]
) -> None:
    configure()
    elsewhere = make_ready(db, OTHER_CASE, "Elsewhere.pdf", ["SYNTHETIC other case."])
    deleted = make_ready(db, SATTVIK, "Deleted.pdf", ["SYNTHETIC deleted."])
    gone = db.get(Document, deleted)
    assert gone is not None
    gone.deleted_at = datetime.now(UTC)
    db.commit()
    for bad in (elsewhere, deleted, uuid.uuid4()):
        refused = start(as_("lead"), [docs[0], bad])
        assert refused.status_code == 422 and refused.json()["code"] == "document-not-eligible"
    too_many = start(as_("lead"), docs)
    assert too_many.status_code == 202
    configure(LEXFLOW_AI_MAX_DOCUMENTS="1")
    assert start(as_("admin"), docs).json()["code"] == "too-many-documents"


def test_client_cases_are_refused_unless_the_owner_allows_client_data(
    as_: As, db: Session, docs: list[uuid.UUID], configure: Callable[..., Settings]
) -> None:
    configure()
    case = db.get(Case, SATTVIK)
    assert case is not None
    case.is_sample = False
    db.commit()
    refused = start(as_("lead"), docs)
    assert refused.status_code == 403 and refused.json()["code"] == "client-data-not-allowed"
    setup = as_("lead").get(f"/api/cases/{SATTVIK}/analysis/setup").json()
    assert setup["canRun"] is False and "sample" in setup["cannotRunReason"]
    configure(LEXFLOW_AI_ALLOW_CLIENT_DATA="true")
    assert start(as_("lead"), docs).status_code == 202


def test_a_run_is_queued_audited_and_one_at_a_time(
    as_: As, db: Session, docs: list[uuid.UUID], configure: Callable[..., Settings]
) -> None:
    configure()
    created = start(as_("lead"), docs)
    assert created.status_code == 202
    run = created.json()
    assert (run["status"], run["provider"], run["model"]) == ("queued", "scripted", "scripted-v1")
    assert run["documentCount"] == 2 and run["result"] is None
    assert run["requestedBy"]["name"] == "Aryan Goyal"
    again = start(as_("associate"), docs)
    assert again.status_code == 409 and again.json()["code"] == "analysis-running"
    (event,) = events(db, "analysis.requested")
    assert event.details == {
        "documents": 2,
        "provider": "scripted",
        "model": "scripted-v1",
        "promptVersion": "case-analysis-v1",
    }
    listed = as_("paralegal").get(runs_url()).json()["items"]
    assert [r["id"] for r in listed] == [run["id"]]


def test_the_hourly_limit_per_person(
    as_: As, db: Session, docs: list[uuid.UUID], configure: Callable[..., Settings]
) -> None:
    configure(LEXFLOW_AI_RUNS_PER_USER_PER_HOUR="1")
    assert start(as_("lead"), docs).status_code == 202
    db.execute(
        update(AnalysisRun).values(
            status="failed", reason_code="x", reason="x", finished_at=datetime.now(UTC)
        )
    )
    db.commit()
    limited = start(as_("lead"), docs)
    assert limited.status_code == 429 and limited.json()["code"] == "rate-limited"
    assert start(as_("associate"), docs).status_code == 202  # the limit is per person


def test_a_run_of_another_case_is_not_found_through_this_case(
    as_: As, db: Session, docs: list[uuid.UUID], configure: Callable[..., Settings]
) -> None:
    configure()
    run_id = start(as_("lead"), docs).json()["id"]
    admin = as_("admin")
    assert admin.get(f"/api/cases/{OTHER_CASE}/analysis-runs/{run_id}").status_code == 404
    assert admin.get(f"{runs_url()}/not-a-uuid").status_code == 404
    assert admin.get(f"{runs_url()}/{uuid.uuid4()}").status_code == 404


# --- the worker -----------------------------------------------------------------------


def test_the_scripted_run_ends_ready_with_verified_sources_only(
    as_: As, db: Session, docs: list[uuid.UUID], configure: Callable[..., Settings]
) -> None:
    settings = configure()
    run_id = start(as_("lead"), docs).json()["id"]
    assert work(db, ScriptedProvider(), settings)
    assert not work(db, ScriptedProvider(), settings)  # nothing else waiting

    body = as_("associate").get(f"{runs_url()}/{run_id}").json()
    assert body["status"] == "ready" and body["finishedAt"]
    result = body["result"]
    assert [f["source"]["documentId"] for f in result["facts"]] == [str(d) for d in docs]
    for f in result["facts"]:
        assert f["source"]["pageNumber"] == 1 and f["source"]["quote"] in (TEXT + REPLY)
    assert result["removed"]["count"] == 1
    assert result["removed"]["reasons"][0]["code"] == "unknown-evidence"
    assert result["precedentsAvailable"] is False and result["precedents"] == []
    assert len(result["contradictions"]) == 1 and len(result["issues"]) == 1
    assert body["evidence"] == {
        "documents": 2,
        "passages": 2,
        "judgmentPassages": 0,
        "characters": body["evidence"]["characters"],
        "truncated": False,
    }

    (done,) = events(db, "analysis.completed")
    assert done.details["providerCalled"] is True and done.details["removed"] == 1
    stored = json.dumps([done.details, db.get(AnalysisRun, uuid.UUID(run_id)).evidence])  # type: ignore[union-attr]
    assert "SYNTHETIC" not in stored  # counts and references only, never text
    assert len(events(db, "analysis.viewed")) == 1


def test_polling_an_unfinished_run_is_not_audited_as_a_view(
    as_: As, db: Session, docs: list[uuid.UUID], configure: Callable[..., Settings]
) -> None:
    configure()
    run_id = start(as_("lead"), docs).json()["id"]
    assert as_("lead").get(f"{runs_url()}/{run_id}").json()["status"] == "queued"
    assert events(db, "analysis.viewed") == []


def test_a_busy_provider_is_retried_later_then_the_run_fails(
    as_: As, db: Session, docs: list[uuid.UUID], configure: Callable[..., Settings]
) -> None:
    settings = configure(LEXFLOW_AI_MAX_ATTEMPTS="2")
    run_id = uuid.UUID(start(as_("lead"), docs).json()["id"])
    busy = ProviderError("provider-rate-limited", "Busy (429).", retry=True)
    provider = ScriptedAnswers([busy, busy])
    assert work(db, provider, settings)
    run = db.get(AnalysisRun, run_id)
    assert run is not None
    db.refresh(run)
    assert (run.status, run.attempts) == ("queued", 1)
    assert run.available_at > datetime.now(UTC) + timedelta(seconds=20)
    assert not work(db, provider, settings)  # not due yet
    run.available_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert work(db, provider, settings)
    db.refresh(run)
    assert (run.status, run.reason_code, run.attempts) == ("failed", "provider-rate-limited", 2)
    assert run.result is None
    (failed,) = events(db, "analysis.failed")
    assert failed.details == {"reason": "provider-rate-limited", "attempts": 2, "model": run.model}


def test_a_refused_request_fails_at_once(
    as_: As, db: Session, docs: list[uuid.UUID], configure: Callable[..., Settings]
) -> None:
    settings = configure()
    run_id = uuid.UUID(start(as_("lead"), docs).json()["id"])
    work(
        db, ScriptedAnswers([ProviderError("provider-auth-failed", "Key refused (403).")]), settings
    )
    body = as_("lead").get(f"{runs_url()}/{run_id}").json()
    assert (body["status"], body["reasonCode"], body["result"]) == (
        "failed",
        "provider-auth-failed",
        None,
    )


def test_an_unreadable_answer_is_asked_for_once_more(
    as_: As, db: Session, docs: list[uuid.UUID], configure: Callable[..., Settings]
) -> None:
    settings = configure()
    good = json.dumps({"facts": [], "insufficient_evidence": True})
    retried = ScriptedAnswers(["not json", good])
    run_id = uuid.UUID(start(as_("lead"), docs).json()["id"])
    work(db, retried, settings)
    run = db.get(AnalysisRun, run_id)
    assert run is not None and run.status == "ready" and len(retried.requests) == 2
    assert run.usage == {"totalTokens": 20}
    assert run.result is not None and run.result["insufficientEvidence"] is True

    run.status, run.reason_code, run.reason = "failed", "x", "x"
    run.result = None
    db.commit()
    second = uuid.UUID(start(as_("lead"), docs).json()["id"])
    truncated = Response(text='{"facts": [', truncated=True)
    work(db, ScriptedAnswers(["[]", truncated]), settings)
    failed = db.get(AnalysisRun, second)
    assert failed is not None and (failed.status, failed.reason_code) == (
        "failed",
        "invalid-output",
    )
    assert failed.result is None


def test_an_answer_citing_an_unknown_judgment_is_stored_without_it(
    as_: As, db: Session, docs: list[uuid.UUID], configure: Callable[..., Settings]
) -> None:
    settings = configure()
    answer = {
        "facts": [
            {
                "id": "F1",
                "statement": "Mark used since 2015.",
                "evidence": "D1",
                "quote": "first used on packaged snack foods in 2015",
            }
        ],
        "precedents": [
            {"evidence": "J3", "summary": "Invented.", "similarities": [], "differences": []}
        ],
    }
    run_id = start(as_("lead"), docs).json()["id"]
    work(db, ScriptedAnswers([json.dumps(answer)]), settings)
    result = as_("lead").get(f"{runs_url()}/{run_id}").json()["result"]
    assert result["precedents"] == [] and len(result["facts"]) == 1
    assert {r["code"]: r["count"] for r in result["removed"]["reasons"]} == {"unknown-judgment": 1}


def test_without_text_at_run_time_no_provider_is_called(
    as_: As, db: Session, docs: list[uuid.UUID], configure: Callable[..., Settings]
) -> None:
    settings = configure()
    run_id = start(as_("lead"), docs).json()["id"]
    for document_id in docs:
        document = db.get(Document, document_id)
        assert document is not None
        document.deleted_at = datetime.now(UTC)
    db.commit()
    never = ScriptedAnswers([])
    work(db, never, settings)
    assert never.requests == []
    result = as_("lead").get(f"{runs_url()}/{run_id}").json()["result"]
    assert (
        result["insufficientEvidence"]
        and "None of the selected documents" in result["insufficientReason"]
    )
    (done,) = events(db, "analysis.completed")
    assert done.details["providerCalled"] is False


def test_the_worker_checks_the_case_again_before_sending_anything(
    as_: As, db: Session, docs: list[uuid.UUID], configure: Callable[..., Settings]
) -> None:
    settings = configure()
    run_id = uuid.UUID(start(as_("lead"), docs).json()["id"])
    case = db.get(Case, SATTVIK)
    assert case is not None
    case.is_sample = False
    db.commit()
    never = ScriptedAnswers([])
    work(db, never, settings)
    run = db.get(AnalysisRun, run_id)
    assert run is not None and (run.status, run.reason_code) == (
        "failed",
        "client-data-not-allowed",
    )
    assert never.requests == []


def test_a_result_is_discarded_when_the_run_is_no_longer_held(
    as_: As, db: Session, docs: list[uuid.UUID], configure: Callable[..., Settings]
) -> None:
    settings = configure()
    run_id = uuid.UUID(start(as_("lead"), docs).json()["id"])
    with shared_sessions(db)() as session:
        claimed = runs.claim(
            session, worker_id="w1", now=datetime.now(UTC), lease_seconds=60, max_attempts=3
        )
    assert claimed == run_id
    run = db.get(AnalysisRun, run_id)
    assert run is not None
    run.worker_id = "w2"  # another worker took the run over
    db.commit()
    status = runs.process(
        shared_sessions(db),
        ScriptedProvider(),
        settings,
        run_id,
        "w1",
        now=lambda: datetime.now(UTC),
    )
    assert status == "discarded"
    db.refresh(run)
    assert run.status == "running" and run.result is None


def test_an_abandoned_run_fails_after_its_last_attempt(
    as_: As, db: Session, docs: list[uuid.UUID], configure: Callable[..., Settings]
) -> None:
    configure()
    run_id = uuid.UUID(start(as_("lead"), docs).json()["id"])
    run = db.get(AnalysisRun, run_id)
    assert run is not None
    run.status, run.attempts, run.worker_id = "running", 3, "dead"
    run.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    with shared_sessions(db)() as session:
        assert (
            runs.claim(
                session, worker_id="w1", now=datetime.now(UTC), lease_seconds=60, max_attempts=3
            )
            is None
        )
    db.refresh(run)
    assert (run.status, run.reason_code) == ("failed", "interrupted")
    assert events(db, "analysis.failed")[0].details == {"reason": "interrupted"}


def test_the_worker_leaves_analysis_alone_when_it_is_unavailable(
    db: Session, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    sessions = shared_sessions(db)
    assert worker.analysis_provider(ai(LEXFLOW_AI_PROVIDER="disabled"), sessions) is None
    gemini = ai(LEXFLOW_AI_PROVIDER="gemini", GEMINI_API_KEY=FAKE_KEY)
    assert worker.analysis_provider(gemini, sessions) is None
    assert "GEMINI_MODEL" in caplog.text and FAKE_KEY not in caplog.text
    monkeypatch.setattr(runs, "table_exists", lambda session: False)
    assert worker.analysis_provider(ai(), sessions) is None
    assert "migration 0011" in caplog.text
    monkeypatch.undo()
    assert isinstance(worker.analysis_provider(ai(), sessions), ScriptedProvider)


def test_the_key_never_reaches_responses_audit_or_openapi(
    app: FastAPI, as_: As, db: Session, docs: list[uuid.UUID], configure: Callable[..., Settings]
) -> None:
    configure(LEXFLOW_AI_PROVIDER="gemini", GEMINI_API_KEY=FAKE_KEY, GEMINI_MODEL="m-1")
    http = as_("lead")
    seen = [
        http.get(f"/api/cases/{SATTVIK}/analysis/setup").text,
        start(http, docs).text,
        http.get(runs_url()).text,
        json.dumps(app.openapi()),
        json.dumps([e.details for e in db.scalars(select(AuditEvent))]),
    ]
    assert all(FAKE_KEY not in text for text in seen)
    assert "GEMINI_API_KEY" not in json.dumps(app.openapi())


def test_the_api_without_migration_0011_answers_clearly(
    as_: As,
    docs: list[uuid.UUID],
    configure: Callable[..., Settings],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure()
    monkeypatch.setattr(runs, "table_exists", lambda session: False)
    setup = as_("lead").get(f"/api/cases/{SATTVIK}/analysis/setup").json()
    assert setup["available"] is False and "0011" in setup["unavailableReason"]
    refused = start(as_("lead"), docs)
    assert refused.status_code == 503 and "0011" in refused.json()["detail"]
    assert as_("lead").get(runs_url()).json() == {"items": []}
    assert as_("lead").get(f"{runs_url()}/{uuid.uuid4()}").status_code == 404


def test_writes_need_the_csrf_header(
    app: FastAPI, people: Any, docs: list[uuid.UUID], configure: Callable[..., Settings]
) -> None:
    configure()
    body = {"documentIds": [str(docs[0])], "confirmTransmission": True}
    with TestClient(app, headers=APP_HEADERS) as http:
        sign_in(http, people["lead"])
        del http.headers["X-LexFlow-Request"]
        refused = http.post(runs_url(), json=body)  # no CSRF header
        assert refused.status_code == 403
        accepted = http.post(runs_url(), json=body, headers=APP_HEADERS)
        assert accepted.status_code == 202
