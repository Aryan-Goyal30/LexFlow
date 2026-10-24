"""The review lifecycle on real runs (Phase 6, Batch 6): analysis by the real
worker with the scripted provider, review, export, then the things that
happen afterwards (re-extraction, deletion, a newer run, access revoked, a
failure mid-write). SYNTHETIC documents; no provider is contacted."""

from __future__ import annotations

import io
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import docx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from lexflow.analysis.scripted import ScriptedProvider
from lexflow.config import Settings
from lexflow.models import (
    AnalysisFindingReview,
    AnalysisFindingReviewEvent,
    AnalysisRun,
    AuditEvent,
    CaseMember,
    Document,
    DocumentChunk,
    User,
)
from lexflow.services import reviews as review_service
from lexflow.services.brief import CHANGED_NOTE
from tests.access_fixtures import SATTVIK
from tests.embedding_fakes import make_ready
from tests.test_analysis_runs import configure, start, work  # noqa: F401 - fixture and helpers

As = Callable[[str], TestClient]
NOTICE = "SYNTHETIC. The plaintiff registered the mark SATTVIK in 2015 and sold snacks under it."
REPLY = "SYNTHETIC. The defendant says the plaintiff first used the mark SATTVIK only in 2017."


@pytest.fixture
def docs(db: Session, people: dict[str, User]) -> list[uuid.UUID]:
    return [
        make_ready(db, SATTVIK, "SYNTHETIC Notice.pdf", [NOTICE]),
        make_ready(db, SATTVIK, "SYNTHETIC Reply.pdf", [REPLY]),
    ]


def analysed(as_: As, db: Session, docs: list[uuid.UUID], settings: Settings) -> AnalysisRun:
    started = start(as_("lead"), docs)
    assert started.status_code == 202, started.text
    assert work(db, ScriptedProvider(), settings)
    run = db.get(AnalysisRun, uuid.UUID(started.json()["id"]))
    assert run is not None
    db.refresh(run)
    assert run.status == "ready"
    return run


def reviews_url(run: AnalysisRun) -> str:
    return f"/api/cases/{SATTVIK}/analysis-runs/{run.id}/reviews"


def decide(http: TestClient, run: AnalysisRun, finding: str, status: str, **extra: Any) -> Any:
    version = next(
        i["version"]
        for i in http.get(reviews_url(run)).json()["items"]
        if i["findingId"] == finding
    )
    return http.put(
        f"{reviews_url(run)}/{finding}",
        json={"status": status, "expectedVersion": version, **extra},
    )


def brief_text(http: TestClient, run: AnalysisRun) -> str:
    response = http.get(f"/api/cases/{SATTVIK}/analysis-runs/{run.id}/brief")
    assert response.status_code == 200, response.text
    return "\n".join(p.text for p in docx.Document(io.BytesIO(response.content)).paragraphs)


@pytest.fixture
def run(
    as_: As,
    db: Session,
    docs: list[uuid.UUID],
    configure: Callable[..., Settings],  # noqa: F811 - the fixture imported from test_analysis_runs
) -> AnalysisRun:
    return analysed(as_, db, docs, configure())


def test_a_worker_run_is_reviewed_and_exported_with_live_sources(as_: As, run: AnalysisRun) -> None:
    lead = as_("lead")
    items = lead.get(reviews_url(run)).json()["items"]
    facts = [i["findingId"] for i in items if i["kind"] == "fact"]
    assert facts == ["F1", "F2"]  # the scripted run's verified facts
    assert decide(lead, run, "F1", "accepted").status_code == 200
    wording = "SYNTHETIC: the reply puts first use in 2017 (lawyer's wording)."
    assert decide(lead, run, "F2", "edited", reviewedText=wording).status_code == 200
    text = brief_text(lead, run)
    assert "SYNTHETIC Notice.pdf" in text and wording in text
    assert CHANGED_NOTE not in text  # the cited chunks still exist with the same text


def test_re_extraction_after_review_is_flagged_and_changes_no_decision(
    as_: As, db: Session, run: AnalysisRun, docs: list[uuid.UUID]
) -> None:
    lead = as_("lead")
    decide(lead, run, "F1", "accepted")
    result_before = dict(run.result or {})
    # Re-extraction replaces a document's chunks: the stored hash no longer matches.
    db.execute(
        update(DocumentChunk)
        .where(DocumentChunk.document_id == docs[0])
        .values(content_sha256="0" * 64)
    )
    db.commit()
    assert CHANGED_NOTE in brief_text(lead, run)
    item = next(i for i in lead.get(reviews_url(run)).json()["items"] if i["findingId"] == "F1")
    assert item["status"] == "accepted" and item["version"] == 1
    db.refresh(run)
    assert run.result == result_before


def test_a_deleted_document_is_flagged_not_replaced(
    as_: As, db: Session, run: AnalysisRun, docs: list[uuid.UUID]
) -> None:
    lead = as_("lead")
    decide(lead, run, "F1", "accepted")
    db.execute(update(Document).where(Document.id == docs[0]).values(deleted_at=datetime.now(UTC)))
    db.commit()
    text = brief_text(lead, run)
    assert CHANGED_NOTE in text and "SYNTHETIC Notice.pdf" in text  # the citation as verified


def test_a_newer_run_starts_unreviewed_and_the_older_keeps_its_decisions(
    as_: As,
    db: Session,
    run: AnalysisRun,
    docs: list[uuid.UUID],
    configure: Callable[..., Settings],  # noqa: F811
) -> None:
    lead = as_("lead")
    decide(lead, run, "F1", "accepted")
    newer = analysed(as_, db, docs, configure())
    assert newer.id != run.id
    assert {i["status"] for i in lead.get(reviews_url(newer)).json()["items"]} == {"unreviewed"}
    older = lead.get(reviews_url(run)).json()["items"]
    assert next(i for i in older if i["findingId"] == "F1")["status"] == "accepted"
    assert "SYNTHETIC Notice.pdf" in brief_text(lead, run)


def test_revoked_access_ends_reviewing_but_keeps_attribution(
    as_: As, db: Session, run: AnalysisRun, people: dict[str, User]
) -> None:
    assert decide(as_("associate"), run, "F1", "accepted").status_code == 200
    db.execute(
        delete(CaseMember).where(
            CaseMember.case_id == SATTVIK, CaseMember.user_id == people["associate"].id
        )
    )
    db.commit()
    assert as_("associate").get(reviews_url(run)).status_code == 404
    assert (
        as_("associate")
        .put(f"{reviews_url(run)}/F2", json={"status": "accepted", "expectedVersion": 0})
        .status_code
        == 404
    )
    item = next(
        i for i in as_("lead").get(reviews_url(run)).json()["items"] if i["findingId"] == "F1"
    )
    assert item["reviewedBy"]["name"] == people["associate"].name


def test_a_failure_mid_write_leaves_no_partial_review(
    as_: As, db: Session, run: AnalysisRun, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = review_service.apply

    def fails_after_writing(*args: Any, **kwargs: Any) -> Any:
        original(*args, **kwargs)
        raise RuntimeError("SYNTHETIC failure after the rows were written")

    monkeypatch.setattr(review_service, "apply", fails_after_writing)
    response = as_("lead").put(
        f"{reviews_url(run)}/F1", json={"status": "accepted", "expectedVersion": 0}
    )
    assert response.status_code == 500
    assert "SYNTHETIC failure" not in response.text  # no internal detail in the answer
    db.expire_all()
    for model in (AnalysisFindingReview, AnalysisFindingReviewEvent):
        assert db.scalar(select(func.count()).select_from(model)) == 0
    assert (
        db.scalars(select(AuditEvent).where(AuditEvent.action == "analysis.finding_reviewed")).all()
        == []
    )
