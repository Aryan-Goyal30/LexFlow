"""Lawyer review of AI findings (Phase 6): decisions, history, access rules,
audit and the matter timeline. SYNTHETIC runs only; no provider is called."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lexflow.models import (
    AnalysisFindingReviewEvent,
    AnalysisRun,
    AuditEvent,
    Case,
    TimelineEvent,
    User,
)
from lexflow.seed import sample_uuid
from lexflow.services import reviews as review_service
from tests.access_fixtures import SATTVIK
from tests.review_fixtures import ready_run, result
from tests.test_portal import as_client, portal_people  # noqa: F401 - fixtures

As = Callable[[str], TestClient]
OTHER_CASE = sample_uuid("case", "case-1001")


@pytest.fixture
def run(db: Session, people: dict[str, User]) -> AnalysisRun:
    return ready_run(db, SATTVIK, requested_by=people["lead"].id)


def url(run: AnalysisRun | str, finding: str | None = None, case: Any = SATTVIK) -> str:
    run_id = run if isinstance(run, str) else str(run.id)
    base = f"/api/cases/{case}/analysis-runs/{run_id}/reviews"
    return f"{base}/{finding}" if finding else base


def decide(
    http: TestClient, run: AnalysisRun, finding: str, status: str, version: int, **extra: Any
) -> Any:
    return http.put(url(run, finding), json={"status": status, "expectedVersion": version, **extra})


def item(body: dict[str, Any], finding: str) -> dict[str, Any]:
    return next(i for i in body["items"] if i["findingId"] == finding)


def events(db: Session, action: str) -> list[AuditEvent]:
    return list(db.scalars(select(AuditEvent).where(AuditEvent.action == action)))


# --- the review lifecycle ------------------------------------------------------------


def test_every_finding_starts_unreviewed(as_: As, run: AnalysisRun) -> None:
    body = as_("lead").get(url(run)).json()
    assert [i["findingId"] for i in body["items"]] == ["F1", "F2", "I1", "P1", "C1"]
    assert {i["status"] for i in body["items"]} == {"unreviewed"}
    assert all(i["version"] == 0 and i["reviewedBy"] is None for i in body["items"])
    assert body["summary"] == {
        "total": 5,
        "unreviewed": 5,
        "accepted": 0,
        "edited": 0,
        "rejected": 0,
    }
    assert body["canReview"] is True
    assert as_("paralegal").get(url(run)).json()["canReview"] is False


def test_accept_edit_reject_and_clear_keep_a_complete_history(
    as_: As, db: Session, run: AnalysisRun, people: dict[str, User]
) -> None:
    lead = as_("lead")
    accepted = decide(lead, run, "F1", "accepted", 0)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted" and accepted.json()["version"] == 1
    assert accepted.json()["reviewedBy"]["name"] == people["lead"].name

    wording = "SYNTHETIC: the mark was registered on 2 February 2015 (lawyer's wording)."
    edited = decide(as_("associate"), run, "F1", "edited", 1, reviewedText=wording, note="checked")
    assert edited.status_code == 200, edited.text
    assert (edited.json()["status"], edited.json()["reviewedText"]) == ("edited", wording)
    rejected = decide(lead, run, "F1", "rejected", 2, note="SYNTHETIC: misreads the plaint")
    assert rejected.json()["status"] == "rejected" and rejected.json()["reviewedText"] is None
    cleared = decide(lead, run, "F1", "unreviewed", 3)
    assert cleared.json()["status"] == "unreviewed" and cleared.json()["version"] == 4

    history = lead.get(f"{url(run, 'F1')}/history").json()["items"]
    assert [(h["version"], h["status"]) for h in history] == [
        (1, "accepted"),
        (2, "edited"),
        (3, "rejected"),
        (4, "unreviewed"),
    ]
    assert history[1]["reviewedText"] == wording and history[1]["note"] == "checked"
    assert history[1]["actor"]["name"] == people["associate"].name

    # The model's wording is the record: the stored result never changes.
    db.refresh(run)
    assert run.result == result()
    assert len(events(db, "analysis.finding_reviewed")) == 4


def test_edit_rules(as_: As, run: AnalysisRun) -> None:
    lead = as_("lead")
    original = result()["facts"][0]["statement"]
    for body, code in (
        ({"reviewedText": "   "}, "reviewed-text-required"),
        ({}, "reviewed-text-required"),
        ({"reviewedText": f"  {original}  "}, "wording-unchanged"),
    ):
        refused = decide(lead, run, "F1", "edited", 0, **body)
        assert (refused.status_code, refused.json()["code"]) == (422, code)
    wording_on_accept = decide(lead, run, "F1", "accepted", 0, reviewedText="x")
    assert wording_on_accept.json()["code"] == "reviewed-text-not-allowed"
    for bad in ({"status": "approved"}, {"status": "accepted", "extra": 1}, {"status": "accepted"}):
        assert lead.put(url(run, "F1"), json=bad).status_code == 422
    too_long = decide(lead, run, "F1", "edited", 0, reviewedText="x" * 2001)
    assert too_long.status_code == 422
    assert lead.get(url(run)).json()["summary"]["unreviewed"] == 5  # nothing was stored


def test_a_stale_version_is_refused_and_a_retry_adds_nothing(
    as_: As, db: Session, run: AnalysisRun
) -> None:
    lead, associate = as_("lead"), as_("associate")
    assert decide(lead, run, "F2", "accepted", 0).status_code == 200
    # The same request again (a retry after a lost response): the version moved on.
    retry = decide(lead, run, "F2", "accepted", 0)
    assert (retry.status_code, retry.json()["code"]) == (409, "review-changed")
    # A second reviewer working from an old copy cannot overwrite the decision.
    late = decide(associate, run, "F2", "rejected", 0, note="late")
    assert late.status_code == 409 and "version 1" in late.json()["detail"]
    # Repeating the current state with the current version changes nothing.
    same = decide(lead, run, "F2", "accepted", 1)
    assert same.status_code == 200 and same.json()["version"] == 1
    count = db.scalar(select(func.count()).select_from(AnalysisFindingReviewEvent))
    assert count == 1
    assert len(events(db, "analysis.finding_reviewed")) == 1


def test_notes_are_private_to_reviewers(as_: As, run: AnalysisRun) -> None:
    note = "SYNTHETIC private note: check the 2017 invoice"
    assert decide(as_("lead"), run, "C1", "rejected", 0, note=note).status_code == 200
    for role in ("lead", "associate", "admin"):
        assert item(as_(role).get(url(run)).json(), "C1")["note"] == note
    paralegal = as_("paralegal")
    seen = paralegal.get(url(run)).json()
    assert item(seen, "C1")["status"] == "rejected" and item(seen, "C1")["note"] is None
    history = paralegal.get(f"{url(run, 'C1')}/history").json()["items"]
    assert history[0]["status"] == "rejected" and history[0]["note"] is None
    assert note not in paralegal.get(f"/api/cases/{SATTVIK}").text


def test_review_ids_are_per_run(
    as_: As, db: Session, run: AnalysisRun, people: dict[str, User]
) -> None:
    newer = ready_run(db, SATTVIK, requested_by=people["lead"].id)
    lead = as_("lead")
    assert decide(lead, run, "F1", "accepted", 0).status_code == 200
    assert decide(lead, newer, "F1", "rejected", 0).status_code == 200
    assert item(lead.get(url(run)).json(), "F1")["status"] == "accepted"
    assert item(lead.get(url(newer)).json(), "F1")["status"] == "rejected"


# --- access ------------------------------------------------------------------------------


def test_only_the_cases_advocates_and_administrators_decide(
    as_: As,
    as_client: As,  # noqa: F811 - the fixture imported from test_portal
    run: AnalysisRun,
) -> None:
    for role, finding in (("admin", "F1"), ("lead", "F2"), ("associate", "I1")):
        assert decide(as_(role), run, finding, "accepted", 0).status_code == 200, role
    paralegal = decide(as_("paralegal"), run, "P1", "accepted", 0)
    assert paralegal.status_code == 403
    for outsider in ("other_advocate", "other_paralegal"):
        assert as_(outsider).get(url(run)).status_code == 404
        assert decide(as_(outsider), run, "P1", "accepted", 0).status_code == 404
    client = as_client("client")
    assert client.get(url(run)).status_code == 403
    assert decide(client, run, "P1", "accepted", 0).status_code == 403


def test_an_archived_case_can_be_read_but_not_reviewed(
    as_: As, db: Session, run: AnalysisRun
) -> None:
    assert decide(as_("lead"), run, "F1", "accepted", 0).status_code == 200
    case = db.get(Case, SATTVIK)
    assert case is not None
    case.archived_at = datetime.now(UTC)
    db.commit()
    body = as_("lead").get(url(run)).json()
    assert body["canReview"] is False and item(body, "F1")["status"] == "accepted"
    refused = decide(as_("lead"), run, "F2", "accepted", 0)
    assert (refused.status_code, refused.json()["code"]) == (409, "case-archived")


def test_runs_and_findings_must_belong_to_the_case(
    as_: As, db: Session, run: AnalysisRun, people: dict[str, User]
) -> None:
    lead = as_("lead")
    elsewhere = ready_run(db, OTHER_CASE, requested_by=people["lead"].id)
    for path in (url(elsewhere), url(str(uuid.uuid4())), url("not-a-uuid")):
        assert lead.get(path).status_code == 404, path
    assert decide(lead, elsewhere, "F1", "accepted", 0).status_code == 404
    for finding in ("F9", "X1", "F0", "D1"):
        response = decide(lead, run, finding, "accepted", 0)
        assert response.status_code == 404, finding
    failed = AnalysisRun(
        case_id=SATTVIK,
        status="failed",
        reason_code="provider-timeout",
        reason="SYNTHETIC",
        provider="scripted",
        model="scripted-v1",
        prompt_version="case-analysis-v2",
        selection={"documentIds": []},
    )
    db.add(failed)
    db.commit()
    not_ready = lead.get(url(failed))
    assert (not_ready.status_code, not_ready.json()["code"]) == (409, "analysis-not-ready")


# --- audit and timeline ----------------------------------------------------------------


def test_decisions_are_audited_without_wording_or_notes(
    as_: As, db: Session, run: AnalysisRun
) -> None:
    secret_note, wording = "SYNTHETIC-NOTE-TEXT", "SYNTHETIC-LAWYER-WORDING"
    decide(as_("lead"), run, "F1", "edited", 0, reviewedText=wording, note=secret_note)
    (event,) = events(db, "analysis.finding_reviewed")
    assert event.details == {
        "finding": "F1",
        "kind": "fact",
        "status": "edited",
        "version": 1,
        "wordingChanged": True,
        "noteChanged": True,
    }
    assert event.target_id == run.id and event.case_id == SATTVIK
    dumped = json.dumps([e.details for e in db.scalars(select(AuditEvent))])
    assert secret_note not in dumped and wording not in dumped


def test_review_actions_appear_on_the_matter_timeline_without_their_content(
    as_: As, db: Session, run: AnalysisRun, people: dict[str, User]
) -> None:
    before = db.scalar(select(func.count()).select_from(TimelineEvent))
    note, wording = "SYNTHETIC-NOTE-TEXT", "SYNTHETIC-LAWYER-WORDING"
    decide(as_("lead"), run, "F1", "edited", 0, reviewedText=wording, note=note)
    decide(as_("lead"), run, "P1", "rejected", 0)
    timeline = as_("paralegal").get(f"/api/cases/{SATTVIK}").json()["timeline"]
    entries = [e for e in timeline if e["kind"] == "review"]
    assert [e["label"] for e in entries] == ["AI finding reviewed", "AI finding reviewed"]
    assert "Fact F1 of the AI analysis of" in entries[0]["description"]
    assert entries[0]["description"].endswith("accepted with the lawyer's wording.")
    assert entries[1]["description"].startswith("Precedent comparison P1")
    assert entries[1]["description"].endswith("rejected.")
    assert entries[0]["actor"]["name"] == people["lead"].name
    shown = json.dumps(timeline)
    assert note not in shown and wording not in shown
    # Not stored as timeline rows: the analysis evidence reads only those.
    assert db.scalar(select(func.count()).select_from(TimelineEvent)) == before
    assert all(e["kind"] == "case" for e in timeline if e not in entries)


def test_without_migration_0012_reviews_are_unavailable_and_nothing_else_breaks(
    as_: As, run: AnalysisRun, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(review_service, "table_exists", lambda session: False)
    response = as_("lead").get(url(run))
    assert (response.status_code, response.json()["code"]) == (503, "review-unavailable")
    assert "migration 0012" in response.json()["detail"]
    detail = as_("lead").get(f"/api/cases/{SATTVIK}")
    assert detail.status_code == 200
    assert all(e["kind"] == "case" for e in detail.json()["timeline"])
