"""Lawyer review of AI analysis findings (Phase 6).

- ``GET  /api/cases/{id}/analysis-runs/{run_id}/reviews``: every finding of
  the run with its current decision, and the counts;
- ``PUT  /api/cases/{id}/analysis-runs/{run_id}/reviews/{finding_id}``:
  accept, edit, reject or clear one finding (with the version seen);
- ``GET  /api/cases/{id}/analysis-runs/{run_id}/reviews/{finding_id}/history``:
  every change, oldest first;
- ``GET  /api/cases/{id}/analysis-runs/{run_id}/brief``: the case brief (DOCX)
  with the accepted findings only (``services/brief.py``); audited as
  ``analysis.brief_exported`` with the counts. No model is called.

Access: reading needs ``view`` on the case; deciding needs
``review-analysis`` (Administrator, lead or associate advocate; not on an
archived case). Notes are shown only to those who may review. Clients never
reach these routes (staff router), and a case the user may not see answers
404. A run of another case, or a finding that is not in the run, also
answers 404. Each recorded change is audited (``analysis.finding_reviewed``,
codes and counts only, never wording or notes).
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from lexflow import authz
from lexflow.analysis import runs
from lexflow.api.analysis import changed_evidence
from lexflow.audit import AuditLog, get_audit_log
from lexflow.auth.deps import require_user
from lexflow.authz import Action, Relation
from lexflow.config import Settings, get_settings
from lexflow.db import get_session
from lexflow.errors import ProblemError, problem_responses
from lexflow.models import AnalysisFindingReview, AnalysisRun, Case, User
from lexflow.schemas import (
    ActorOut,
    AnalysisReviewHistoryEntryOut,
    AnalysisReviewHistoryOut,
    AnalysisReviewIn,
    AnalysisReviewListOut,
    AnalysisReviewOut,
    AnalysisReviewSummaryOut,
)
from lexflow.services import brief as brief_service
from lexflow.services import cases as case_service
from lexflow.services import reviews

router = APIRouter(tags=["analysis"])

RUN_NOT_FOUND = "No analysis run with this id exists for this case."
FINDING_NOT_FOUND = "No finding with this id exists in this analysis."
NOT_READY = "Only a finished analysis can be reviewed."
ANALYSIS_MIGRATION_MISSING = (
    "AI analysis needs a database update (migration 0011) that is not applied yet."
)
_FINDING_ID = re.compile(r"[FIPC][1-9][0-9]{0,3}")
_SPACE = re.compile(r"\s+")


def _now() -> datetime:
    return datetime.now(UTC)


def _available(session: Session) -> None:
    if not runs.table_exists(session):
        raise ProblemError(503, "analysis-unavailable", ANALYSIS_MIGRATION_MISSING)
    if not reviews.table_exists(session):
        raise ProblemError(503, "review-unavailable", reviews.MIGRATION_MISSING)


def _ready_run(session: Session, case: Case, run_id: str) -> AnalysisRun:
    try:
        parsed = uuid.UUID(run_id)
    except ValueError:
        raise ProblemError(404, "analysis-run-not-found", RUN_NOT_FOUND) from None
    run = session.get(AnalysisRun, parsed)
    if run is None or run.case_id != case.id:
        raise ProblemError(404, "analysis-run-not-found", RUN_NOT_FOUND)
    if run.status != "ready" or run.result is None:
        raise ProblemError(409, "analysis-not-ready", NOT_READY)
    return run


def _finding(run: AnalysisRun, finding_id: str) -> reviews.Finding:
    found = reviews.finding(run.result, finding_id) if _FINDING_ID.fullmatch(finding_id) else None
    if found is None:
        raise ProblemError(404, "finding-not-found", FINDING_NOT_FOUND)
    return found


def _people(session: Session, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, User]:
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    return {u.id: u for u in session.scalars(select(User).where(User.id.in_(wanted)))}


def _actor(people: dict[uuid.UUID, User], user_id: uuid.UUID | None) -> ActorOut | None:
    who = people.get(user_id) if user_id is not None else None
    return ActorOut(id=who.id, name=who.name) if who is not None else None


def may_see_notes(rel: Relation) -> bool:
    return authz.allows(rel, Action.REVIEW_ANALYSIS)


def _out(
    item: reviews.Finding,
    review: AnalysisFindingReview | None,
    people: dict[uuid.UUID, User],
    *,
    notes: bool,
) -> AnalysisReviewOut:
    if review is None:
        return AnalysisReviewOut(
            finding_id=item.id,
            kind=item.kind,  # type: ignore[arg-type]  # one of FINDING_KINDS
            status="unreviewed",
            reviewed_text=None,
            note=None,
            version=0,
            reviewed_by=None,
            reviewed_at=None,
        )
    return AnalysisReviewOut(
        finding_id=item.id,
        kind=item.kind,  # type: ignore[arg-type]
        status=review.status,  # type: ignore[arg-type]  # the database checks the value
        reviewed_text=review.reviewed_text,
        note=review.note if notes else None,
        version=review.version,
        reviewed_by=_actor(people, review.reviewed_by_id),
        reviewed_at=review.reviewed_at,
    )


@router.get(
    "/cases/{case_id}/analysis-runs/{run_id}/reviews",
    response_model=AnalysisReviewListOut,
    responses=problem_responses(404, 409, 503),
)
def list_reviews(
    case_id: str,
    run_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
) -> AnalysisReviewListOut:
    """Every finding of a finished run with its current review decision."""
    case, rel = authz.load_case(
        session, user, case_service.parse_case_id(case_id), Action.VIEW, audit
    )
    _available(session)
    run = _ready_run(session, case, run_id)
    stored = reviews.current(session, run.id)
    people = _people(session, {r.reviewed_by_id for r in stored.values()})
    notes = may_see_notes(rel)
    items = [_out(f, stored.get(f.id), people, notes=notes) for f in reviews.findings(run.result)]
    return AnalysisReviewListOut(
        run_id=run.id,
        can_review=authz.allows(rel, Action.REVIEW_ANALYSIS) and case.archived_at is None,
        summary=AnalysisReviewSummaryOut(**reviews.summary(i.status for i in items)),
        items=items,
    )


@router.put(
    "/cases/{case_id}/analysis-runs/{run_id}/reviews/{finding_id}",
    response_model=AnalysisReviewOut,
    responses=problem_responses(403, 404, 409, 422, 503),
)
def review_finding(
    case_id: str,
    run_id: str,
    finding_id: str,
    body: AnalysisReviewIn,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
) -> AnalysisReviewOut:
    """Accept, edit, reject or clear one finding. The run's stored result is
    never changed; every change is kept in the finding's history."""
    case, _ = authz.load_case(
        session, user, case_service.parse_case_id(case_id), Action.REVIEW_ANALYSIS, audit
    )
    _available(session)
    run = _ready_run(session, case, run_id)
    item = _finding(run, finding_id)
    if body.status == "edited":
        wording = (body.reviewed_text or "").strip()
        if not wording:
            raise ProblemError(
                422, "reviewed-text-required", "Enter the wording you accept for this finding."
            )
        if _SPACE.sub(" ", wording) == _SPACE.sub(" ", item.text.strip()):
            raise ProblemError(
                422,
                "wording-unchanged",
                "The wording is unchanged from the AI's; accept the finding instead.",
            )
    elif body.reviewed_text is not None:
        raise ProblemError(
            422,
            "reviewed-text-not-allowed",
            "Only an edited finding has the lawyer's own wording.",
        )
    change = reviews.normalised(body.status, body.reviewed_text, body.note)
    try:
        with session.begin_nested():
            outcome = reviews.apply(
                session,
                run,
                item,
                change,
                expected_version=body.expected_version,
                actor_id=user.id,
                now=_now(),
            )
    except reviews.StaleVersionError as stale:
        raise ProblemError(
            409,
            "review-changed",
            "This finding was reviewed again in the meantime "
            f"(now version {stale.current_version}). Reload it and try again.",
        ) from None
    except IntegrityError:
        raise ProblemError(
            409,
            "review-changed",
            "This finding was reviewed again in the meantime. Reload it and try again.",
        ) from None
    session.commit()
    if outcome.changed and outcome.review is not None:
        audit.record(
            "analysis.finding_reviewed",
            actor=user,
            target_type="analysis_run",
            target_id=run.id,
            case_id=case.id,
            details={
                "finding": item.id,
                "kind": item.kind,
                "status": change.status,
                "version": outcome.review.version,
                "wordingChanged": outcome.wording_changed,
                "noteChanged": outcome.note_changed,
            },
        )
    people = _people(session, {user.id})
    return _out(item, outcome.review, people, notes=True)


@router.get(
    "/cases/{case_id}/analysis-runs/{run_id}/reviews/{finding_id}/history",
    response_model=AnalysisReviewHistoryOut,
    responses=problem_responses(404, 409, 503),
)
def review_history(
    case_id: str,
    run_id: str,
    finding_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
) -> AnalysisReviewHistoryOut:
    """Every recorded change to one finding's review, oldest first."""
    case, rel = authz.load_case(
        session, user, case_service.parse_case_id(case_id), Action.VIEW, audit
    )
    _available(session)
    run = _ready_run(session, case, run_id)
    item = _finding(run, finding_id)
    events = reviews.history(session, run.id, item.id)
    people = _people(session, {e.actor_id for e in events})
    notes = may_see_notes(rel)
    return AnalysisReviewHistoryOut(
        finding_id=item.id,
        items=[
            AnalysisReviewHistoryEntryOut(
                version=e.version,
                status=e.status,  # type: ignore[arg-type]
                reviewed_text=e.reviewed_text,
                note=e.note if notes else None,
                actor=_actor(people, e.actor_id),
                occurred_at=e.occurred_at,
            )
            for e in events
        ],
    )


@router.get(
    "/cases/{case_id}/analysis-runs/{run_id}/brief",
    response_class=Response,
    responses={
        200: {
            "content": {brief_service.DOCX_MEDIA_TYPE: {}},
            "description": "The case brief as a Word document.",
        },
        **problem_responses(404, 409, 503),
    },
)
def export_brief(
    case_id: str,
    run_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    settings: Settings = Depends(get_settings),
) -> Response:
    """The case brief (DOCX): the findings a lawyer accepted, with their
    citations; unreviewed and rejected findings are left out and counted.
    Generated here, on request; no model is called."""
    case, _ = authz.load_case(
        session, user, case_service.parse_case_id(case_id), Action.VIEW, audit
    )
    _available(session)
    run = _ready_run(session, case, run_id)
    stored = reviews.current(session, run.id)
    tally = brief_service.counts(reviews.findings(run.result), stored)
    if tally.included == 0:
        raise ProblemError(
            409,
            "no-accepted-findings",
            "No finding of this analysis has been accepted yet. The brief contains only "
            "findings a lawyer accepted.",
        )
    items = (run.evidence or {}).get("items", {})
    changed = set(changed_evidence(session, items)) if isinstance(items, dict) else set()
    people = _people(session, {r.reviewed_by_id for r in stored.values()})
    now = _now()
    content = brief_service.build(
        case=case,
        run=run,
        reviews=stored,
        people=people,
        changed=changed,
        prepared_by=user,
        now=now,
        zone=settings.timezone,
    )
    audit.record(
        "analysis.brief_exported",
        actor=user,
        target_type="analysis_run",
        target_id=run.id,
        case_id=case.id,
        details={
            "accepted": tally.accepted,
            "edited": tally.edited,
            "rejected": tally.rejected,
            "unreviewed": tally.unreviewed,
        },
    )
    day = now.astimezone(ZoneInfo(settings.timezone)).date().isoformat()
    return Response(
        content,
        media_type=brief_service.DOCX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{brief_service.filename(case, day)}"',
            "Cache-Control": "no-store",
        },
    )
