"""The review tables of Phase 6 (migration 0012): the database itself refuses
ambiguous, duplicate or inconsistent review rows. SYNTHETIC runs only."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from lexflow.models import AnalysisFindingReview, AnalysisFindingReviewEvent, AnalysisRun, User
from tests.access_fixtures import SATTVIK
from tests.review_fixtures import ready_run


@pytest.fixture
def run(db: Session, people: dict[str, User]) -> AnalysisRun:
    return ready_run(db, SATTVIK, requested_by=people["lead"].id)


def review(run: AnalysisRun, **changes: Any) -> AnalysisFindingReview:
    values: dict[str, Any] = {
        "run_id": run.id,
        "case_id": run.case_id,
        "finding_kind": "fact",
        "finding_id": "F1",
        "status": "accepted",
        "version": 1,
        "reviewed_at": datetime.now(UTC),
        **changes,
    }
    return AnalysisFindingReview(**values)


def refused(db: Session, row: Any) -> None:
    db.add(row)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_a_review_is_stored_beside_the_unchanged_result(db: Session, run: AnalysisRun) -> None:
    original = dict(run.result or {})
    db.add(review(run, status="edited", reviewed_text="SYNTHETIC lawyer wording.", note="checked"))
    db.commit()
    db.refresh(run)
    assert run.result == original  # the model's wording stays the record


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "approved"},  # not a review status
        {"status": "edited"},  # an edit needs the lawyer's wording
        {"status": "accepted", "reviewed_text": "text"},  # wording only for edits
        {"finding_kind": "issue", "finding_id": "F1"},  # kind and id disagree
        {"finding_kind": "summary", "finding_id": "S1"},  # not a kind of finding
        {"finding_id": "F0"},
        {"finding_id": "D1"},  # evidence ids are not findings
        {"finding_id": "F12345"},
        {"version": 0},
        {"note": ""},  # empty notes are stored as NULL, never as ''
        {"note": "x" * 2001},
        {"status": "edited", "reviewed_text": "x" * 2001},
    ],
)
def test_inconsistent_review_rows_are_refused(
    db: Session, run: AnalysisRun, changes: dict[str, Any]
) -> None:
    refused(db, review(run, **changes))


def test_one_review_per_finding_of_a_run(
    db: Session, run: AnalysisRun, people: dict[str, User]
) -> None:
    db.add(review(run))
    db.commit()
    refused(db, review(run, status="rejected"))
    # The same id in another run is another finding: ids are unique only within a run.
    other = ready_run(db, SATTVIK, requested_by=people["lead"].id)
    db.add(review(other))
    db.commit()


def test_history_entries_are_unique_per_version(db: Session, run: AnalysisRun) -> None:
    current = review(run)
    db.add(current)
    db.flush()

    def event(version: int) -> AnalysisFindingReviewEvent:
        return AnalysisFindingReviewEvent(
            review_id=current.id,
            run_id=run.id,
            case_id=run.case_id,
            finding_kind="fact",
            finding_id="F1",
            status="accepted",
            version=version,
        )

    db.add(event(1))
    db.commit()
    refused(db, event(1))  # a retried write cannot add a second entry for one change
    db.add(event(2))
    db.commit()


def test_a_review_must_point_at_an_existing_run(db: Session, run: AnalysisRun) -> None:
    refused(db, review(run, run_id=uuid.uuid4()))
