"""Lawyer review of AI analysis findings (Phase 6).

A finding is one item of a ready run's validated result: a fact (F1…), an
issue (I1…), a precedent comparison (P1…) or a contradiction (C1…). Ids are
unique only within a run, so a finding is always addressed by run *and* id.

Rules:

- the run's ``result`` is never changed; a decision and any lawyer wording
  are stored beside it (``AnalysisFindingReview``), and every change adds an
  entry to the append-only history (``AnalysisFindingReviewEvent``) in the
  same transaction;
- statuses: ``unreviewed`` (no decision, or a cleared one), ``accepted``,
  ``edited`` (accepted with the lawyer's wording) and ``rejected``;
- every change names the version it saw; a stale version is refused, and a
  change that alters nothing is not recorded again (a retry is harmless);
- notes are private to reviewers: never on the timeline, in audit details or
  in a case brief.

Review actions appear on the matter timeline as entries derived from the
history (``timeline_entries``). They are not ``timeline_events`` rows, which
the analysis evidence sends to the model, so review content never becomes
model input.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from lexflow.models import AnalysisFindingReview, AnalysisFindingReviewEvent, AnalysisRun

MIGRATION_MISSING = (
    "Reviewing findings needs a database update (migration 0012) that is not applied yet."
)
KIND_LABEL = {
    "fact": "Fact",
    "issue": "Issue",
    "precedent": "Precedent comparison",
    "contradiction": "Contradiction",
}
# Where each kind's list and main wording are in a stored result.
_LISTS = (
    ("fact", "facts", "statement"),
    ("issue", "issues", "question"),
    ("precedent", "precedents", "summary"),
    ("contradiction", "contradictions", "description"),
)


def table_exists(session: Session) -> bool:
    """False before migration 0012: reviewing is then unavailable, nothing fails."""
    return session.scalar(text("SELECT to_regclass('analysis_finding_reviews')")) is not None


@dataclass(frozen=True)
class Finding:
    kind: str
    id: str
    text: str  # the model's wording, as validated and stored with the run
    item: dict[str, Any]  # the whole stored item (sources, metadata)


def findings(result: dict[str, Any] | None) -> list[Finding]:
    """Every finding of a stored result, in display order."""
    found: list[Finding] = []
    for kind, key, field in _LISTS:
        for item in (result or {}).get(key) or []:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                found.append(Finding(kind, item["id"], str(item.get(field, "")), item))
    return found


def finding(result: dict[str, Any] | None, finding_id: str) -> Finding | None:
    return next((f for f in findings(result) if f.id == finding_id), None)


def current(session: Session, run_id: uuid.UUID) -> dict[str, AnalysisFindingReview]:
    rows = session.scalars(
        select(AnalysisFindingReview).where(AnalysisFindingReview.run_id == run_id)
    )
    return {r.finding_id: r for r in rows}


class StaleVersionError(Exception):
    """The review changed since the version the request was based on."""

    def __init__(self, current_version: int) -> None:
        super().__init__(current_version)
        self.current_version = current_version


@dataclass(frozen=True)
class Change:
    status: str
    reviewed_text: str | None
    note: str | None


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def normalised(status: str, reviewed_text: str | None, note: str | None) -> Change:
    return Change(status, _clean(reviewed_text) if status == "edited" else None, _clean(note))


@dataclass(frozen=True)
class Outcome:
    review: AnalysisFindingReview | None  # None: still unreviewed, nothing stored
    changed: bool
    wording_changed: bool = False
    note_changed: bool = False


def apply(
    session: Session,
    run: AnalysisRun,
    item: Finding,
    change: Change,
    *,
    expected_version: int,
    actor_id: uuid.UUID,
    now: datetime,
) -> Outcome:
    """Record one decision (flushes, does not commit). Raises StaleVersionError
    when the stored version differs from ``expected_version``."""
    review = session.scalars(
        select(AnalysisFindingReview)
        .where(AnalysisFindingReview.run_id == run.id, AnalysisFindingReview.finding_id == item.id)
        .with_for_update()
    ).one_or_none()
    version = review.version if review is not None else 0
    if expected_version != version:
        raise StaleVersionError(version)
    before = (
        Change(review.status, review.reviewed_text, review.note)
        if review is not None
        else Change("unreviewed", None, None)
    )
    if change == before:
        return Outcome(review, changed=False)
    if review is None:
        review = AnalysisFindingReview(
            run_id=run.id,
            case_id=run.case_id,
            finding_kind=item.kind,
            finding_id=item.id,
            version=0,
        )
        session.add(review)
    review.status = change.status
    review.reviewed_text = change.reviewed_text
    review.note = change.note
    review.version = version + 1
    review.reviewed_by_id = actor_id
    review.reviewed_at = now
    session.flush()  # the unique constraint refuses a concurrent first decision
    session.add(
        AnalysisFindingReviewEvent(
            review_id=review.id,
            run_id=run.id,
            case_id=run.case_id,
            finding_kind=item.kind,
            finding_id=item.id,
            status=change.status,
            reviewed_text=change.reviewed_text,
            note=change.note,
            version=review.version,
            actor_id=actor_id,
            occurred_at=now,
        )
    )
    session.flush()
    return Outcome(
        review,
        changed=True,
        wording_changed=change.reviewed_text != before.reviewed_text,
        note_changed=change.note != before.note,
    )


def history(
    session: Session, run_id: uuid.UUID, finding_id: str
) -> list[AnalysisFindingReviewEvent]:
    return list(
        session.scalars(
            select(AnalysisFindingReviewEvent)
            .where(
                AnalysisFindingReviewEvent.run_id == run_id,
                AnalysisFindingReviewEvent.finding_id == finding_id,
            )
            .order_by(AnalysisFindingReviewEvent.version)
        )
    )


def summary(items: Iterable[str]) -> dict[str, int]:
    counts = {"total": 0, "unreviewed": 0, "accepted": 0, "edited": 0, "rejected": 0}
    for status in items:
        counts["total"] += 1
        counts[status] += 1
    return counts


@dataclass(frozen=True)
class TimelineEntry:
    id: uuid.UUID
    day: date
    label: str
    description: str
    actor_id: uuid.UUID | None
    recorded_at: datetime


_VERB = {
    "accepted": "accepted",
    "edited": "accepted with the lawyer's wording",
    "rejected": "rejected",
    "unreviewed": "returned to unreviewed",
}


def timeline_entries(session: Session, case_id: uuid.UUID, zone: str) -> list[TimelineEntry]:
    """Review actions for the matter timeline: who decided what about which
    finding of which run, never the wording or the note."""
    if not table_exists(session):
        return []
    rows = session.execute(
        select(AnalysisFindingReviewEvent, AnalysisRun.created_at)
        .join(AnalysisRun, AnalysisRun.id == AnalysisFindingReviewEvent.run_id)
        .where(AnalysisFindingReviewEvent.case_id == case_id)
    ).all()
    tz = ZoneInfo(zone)
    entries: list[TimelineEntry] = []
    for event, run_created in rows:
        run_day = run_created.astimezone(tz).strftime("%d %b %Y").lstrip("0")
        name = f"{KIND_LABEL[event.finding_kind]} {event.finding_id}"
        entries.append(
            TimelineEntry(
                id=event.id,
                day=event.occurred_at.astimezone(tz).date(),
                label="AI finding reviewed",
                description=f"{name} of the AI analysis of {run_day} {_VERB[event.status]}.",
                actor_id=event.actor_id,
                recorded_at=event.occurred_at,
            )
        )
    return entries
