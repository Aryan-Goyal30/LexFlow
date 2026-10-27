"""Outcome assessments of a reviewed analysis run (Phase 7: synthetic engineering demo).

- ``GET  /api/cases/{id}/analysis-runs/{run_id}/assessments``: the run's
  assessments, newest first, with their review state and what is needed to
  generate one;
- ``POST /api/cases/{id}/analysis-runs/{run_id}/assessments``: generate one
  now (201), from the run's accepted findings and precedents only;
- ``GET  /api/cases/{id}/analysis-runs/{run_id}/assessments/{assessment_id}``;
- ``PUT  …/assessments/{assessment_id}/review``: accept, edit (the summary),
  reject or clear, with the version seen (Phase 6 rules);
- ``GET  …/assessments/{assessment_id}/review/history``: every change.

**Off by default.** Unless ``LEXFLOW_OUTCOME_ASSESSMENT`` is true (allowed only
with a test or e2e database) and migration 0013 is applied, every route here
answers 404 exactly like a route that does not exist, and nothing about
assessments appears anywhere else.

Access: reading needs ``view`` on the case (notes only for those who may
review); generating needs ``run-assessment`` and deciding ``review-assessment``
(Administrator, lead or associate advocate; not on an archived case).
Clients never reach these routes (staff router); a case the user may not see,
a run of another case or an assessment of another run answer 404. Audited:
``assessment.requested``, ``assessment.completed``, ``assessment.failed`` and
``assessment.reviewed``, with codes and counts only.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from lexflow import authz
from lexflow.analysis.provider import Unavailable, client_data_allowed
from lexflow.api.analysis import assessment_enabled
from lexflow.assessment import inputs as inputs_mod
from lexflow.assessment import provider as provider_mod
from lexflow.assessment import service
from lexflow.audit import AuditLog, get_audit_log
from lexflow.auth.deps import require_user
from lexflow.authz import Action, Relation
from lexflow.config import Settings, get_settings
from lexflow.db import get_session
from lexflow.domain import ADMINISTRATOR
from lexflow.errors import ProblemError, problem_responses
from lexflow.models import AnalysisRun, Case, OutcomeAssessment, OutcomeAssessmentReview, User
from lexflow.schemas import (
    ActorOut,
    AnalysisRemovedOut,
    AnalysisReviewHistoryEntryOut,
    AssessmentListOut,
    AssessmentOut,
    AssessmentResultOut,
    AssessmentReviewHistoryOut,
    AssessmentReviewIn,
    AssessmentReviewOut,
)
from lexflow.services import cases as case_service
from lexflow.services import reviews as finding_reviews

RUN_NOT_FOUND = "No analysis run with this id exists for this case."
ASSESSMENT_NOT_FOUND = "No assessment with this id exists for this analysis."
NOT_READY = "Only a finished analysis can be assessed."
NOT_REVIEWABLE = "Only a ready assessment can be reviewed; this one has no assessment to accept."
HISTORY_MAX = 50


def _now() -> datetime:
    return datetime.now(UTC)


def _enabled_or_not_found(
    settings: Settings = Depends(get_settings), session: Session = Depends(get_session)
) -> None:
    """The effective flag (setting and migration 0013, D7-1), shared with the setup.
    A router dependency, so it runs before the request body is read: with the
    flag off every route answers exactly what a route that does not exist
    answers, never a validation error that would reveal it."""
    if not assessment_enabled(settings, session):
        raise StarletteHTTPException(status_code=404)


router = APIRouter(tags=["assessment"], dependencies=[Depends(_enabled_or_not_found)])


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


def _assessment(session: Session, run: AnalysisRun, assessment_id: str) -> OutcomeAssessment:
    try:
        parsed = uuid.UUID(assessment_id)
    except ValueError:
        raise ProblemError(404, "assessment-not-found", ASSESSMENT_NOT_FOUND) from None
    found = session.get(OutcomeAssessment, parsed)
    if found is None or found.run_id != run.id:
        raise ProblemError(404, "assessment-not-found", ASSESSMENT_NOT_FOUND)
    return found


def _people(session: Session, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, User]:
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    return {u.id: u for u in session.scalars(select(User).where(User.id.in_(wanted)))}


def _actor(people: dict[uuid.UUID, User], user_id: uuid.UUID | None) -> ActorOut | None:
    who = people.get(user_id) if user_id is not None else None
    return ActorOut(id=who.id, name=who.name) if who is not None else None


def _review_out(
    review: OutcomeAssessmentReview | None, people: dict[uuid.UUID, User], *, notes: bool
) -> AssessmentReviewOut:
    if review is None:
        return AssessmentReviewOut(
            status="unreviewed",
            reviewed_text=None,
            note=None,
            version=0,
            reviewed_by=None,
            reviewed_at=None,
        )
    return AssessmentReviewOut(
        status=review.status,  # type: ignore[arg-type]  # the database checks the value
        reviewed_text=review.reviewed_text,
        note=review.note if notes else None,
        version=review.version,
        reviewed_by=_actor(people, review.reviewed_by_id),
        reviewed_at=review.reviewed_at,
    )


def _out(
    assessment: OutcomeAssessment,
    review: OutcomeAssessmentReview | None,
    people: dict[uuid.UUID, User],
    *,
    notes: bool,
    current: dict[str, Any],
) -> AssessmentOut:
    pipeline = (assessment.inputs or {}).get("pipeline") or {}
    excluded = (assessment.inputs or {}).get("excluded") or {}
    return AssessmentOut(
        id=assessment.id,
        run_id=assessment.run_id,
        status=assessment.status,  # type: ignore[arg-type]
        reason_code=assessment.reason_code,
        reason=assessment.reason,
        provider=assessment.provider,
        provider_label=provider_mod.PROVIDER_LABELS.get(assessment.provider),
        model=assessment.model,
        prompt_version=assessment.prompt_version,
        schema_version=pipeline.get("schemaVersion"),
        validator_version=pipeline.get("validatorVersion"),
        requested_by=_actor(people, assessment.requested_by_id),
        created_at=assessment.created_at,
        inputs_changed=service.inputs_changed(assessment, current),
        excluded={str(k): int(v) for k, v in excluded.items()},
        removed=(
            AnalysisRemovedOut.model_validate(assessment.removed) if assessment.removed else None
        ),
        result=(
            AssessmentResultOut.model_validate(assessment.result)
            if assessment.status == "ready" and assessment.result is not None
            else None
        ),
        review=_review_out(review, people, notes=notes),
    )


def may_see_notes(rel: Relation) -> bool:
    return authz.allows(rel, Action.REVIEW_ASSESSMENT)


def _cannot_generate(
    settings: Settings,
    session: Session,
    user: User,
    rel: Relation,
    case: Case,
    gathered: inputs_mod.Inputs,
) -> str | None:
    provider = provider_mod.provider_for(settings)
    if isinstance(provider, Unavailable):
        if user.role == ADMINISTRATOR and provider.detail:
            return f"{provider.reason} ({provider.detail})"
        return provider.reason
    if not authz.allows(rel, Action.RUN_ASSESSMENT):
        return "Only the case's advocates and administrators may generate an assessment."
    if case.archived_at is not None:
        return "This case is archived."
    if not provider_mod.allowed_for(settings, case.id):
        return "Outcome assessment is enabled on this server only for cases the owner approved."
    if not case.is_sample and not client_data_allowed(settings, case.id):
        return (
            "Only sample (fictional) cases may be assessed on this server until a privacy "
            "review allows client material."
        )
    gate = gathered.gate(case.id in settings.ai_approved_case_ids)
    if gate is not None:
        return inputs_mod.GATE_REASONS[gate]
    return None


@router.get(
    "/cases/{case_id}/analysis-runs/{run_id}/assessments",
    response_model=AssessmentListOut,
    responses=problem_responses(404, 409),
)
def list_assessments(
    case_id: str,
    run_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    settings: Settings = Depends(get_settings),
) -> AssessmentListOut:
    """The run's assessments, newest first, and whether one can be generated now."""
    case, rel = authz.load_case(
        session, user, case_service.parse_case_id(case_id), Action.VIEW, audit
    )
    run = _ready_run(session, case, run_id)
    gathered = inputs_mod.gather(session, run)
    current = gathered.record()
    rows = list(
        session.scalars(
            select(OutcomeAssessment)
            .where(OutcomeAssessment.run_id == run.id)
            .order_by(OutcomeAssessment.created_at.desc(), OutcomeAssessment.id.desc())
            .limit(HISTORY_MAX)
        )
    )
    decided = {
        r.assessment_id: r
        for r in session.scalars(
            select(OutcomeAssessmentReview).where(
                OutcomeAssessmentReview.assessment_id.in_([a.id for a in rows])
            )
        )
    }
    people = _people(
        session,
        {a.requested_by_id for a in rows} | {r.reviewed_by_id for r in decided.values()},
    )
    notes = may_see_notes(rel)
    cannot = _cannot_generate(settings, session, user, rel, case, gathered)
    return AssessmentListOut(
        run_id=run.id,
        can_generate=cannot is None,
        cannot_generate_reason=cannot,
        can_review=authz.allows(rel, Action.REVIEW_ASSESSMENT) and case.archived_at is None,
        accepted_findings=len(gathered.findings),
        accepted_precedents=len(gathered.precedents),
        items=[_out(a, decided.get(a.id), people, notes=notes, current=current) for a in rows],
    )


@router.post(
    "/cases/{case_id}/analysis-runs/{run_id}/assessments",
    response_model=AssessmentOut,
    status_code=status.HTTP_201_CREATED,
    responses=problem_responses(403, 404, 409, 429, 503),
)
def generate_assessment(
    case_id: str,
    run_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    settings: Settings = Depends(get_settings),
) -> AssessmentOut:
    """Assess the run now from its accepted findings and precedents only. With
    no accepted finding or precedent the assessment is stored as
    'insufficient' and no provider is called."""
    case, _ = authz.load_case(
        session, user, case_service.parse_case_id(case_id), Action.RUN_ASSESSMENT, audit
    )
    provider = provider_mod.provider_for(settings)
    if isinstance(provider, Unavailable):
        reason = provider.reason
        if user.role == ADMINISTRATOR and provider.detail:
            reason = f"{reason} ({provider.detail})"
        raise ProblemError(503, provider.code, reason)
    run = _ready_run(session, case, run_id)
    if not provider_mod.allowed_for(settings, case.id):
        raise ProblemError(
            403, "assessment-not-approved", "Outcome assessment is not enabled for this case."
        )
    if not case.is_sample and not client_data_allowed(settings, case.id):
        raise ProblemError(
            403,
            "client-data-not-allowed",
            "Only sample (fictional) cases may be assessed on this server.",
        )
    now = _now()
    if (
        service.created_since(session, user.id, now - timedelta(hours=1))
        >= settings.ai_runs_per_user_per_hour
    ):
        raise ProblemError(
            429,
            "assessment-rate-limited",
            "You have generated the most assessments allowed in one hour. Try again later.",
        )
    generated = service.generate(
        session,
        run,
        provider,
        requested_by=user.id,
        now=now,
        allow_genuine=case.id in settings.ai_approved_case_ids,
    )
    assessment = generated.assessment
    session.commit()
    recorded = assessment.inputs or {}
    audit.record(
        "assessment.requested",
        actor=user,
        target_type="analysis_run",
        target_id=run.id,
        case_id=case.id,
        details={
            "assessment": str(assessment.id),
            "acceptedFindings": len(recorded.get("findings") or []),
            "acceptedPrecedents": len(recorded.get("precedents") or []),
        },
    )
    result = assessment.result or {}
    if assessment.status == "failed":
        audit.record(
            "assessment.failed",
            actor=user,
            outcome="failed",
            target_type="analysis_run",
            target_id=run.id,
            case_id=case.id,
            details={"assessment": str(assessment.id), "reason": assessment.reason_code or ""},
        )
    else:
        audit.record(
            "assessment.completed",
            actor=user,
            target_type="analysis_run",
            target_id=run.id,
            case_id=case.id,
            details={
                "assessment": str(assessment.id),
                "status": assessment.status,
                "reason": assessment.reason_code or "",
                "providerCalled": generated.called,
                "provider": assessment.provider,
                "model": assessment.model,
                "uncertainty": str(result.get("uncertainty") or ""),
                "precedents": len(result.get("precedents") or []),
                "steps": len(result.get("reasoning") or []),
                "removed": int((assessment.removed or {}).get("count") or 0),
            },
        )
    people = _people(session, {user.id})
    return _out(
        assessment,
        None,
        people,
        notes=True,
        current=service.current_inputs(session, run),
    )


@router.get(
    "/cases/{case_id}/analysis-runs/{run_id}/assessments/{assessment_id}",
    response_model=AssessmentOut,
    responses=problem_responses(404, 409),
)
def get_assessment(
    case_id: str,
    run_id: str,
    assessment_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    settings: Settings = Depends(get_settings),
) -> AssessmentOut:
    case, rel = authz.load_case(
        session, user, case_service.parse_case_id(case_id), Action.VIEW, audit
    )
    run = _ready_run(session, case, run_id)
    assessment = _assessment(session, run, assessment_id)
    review = service.current_review(session, assessment.id)
    people = _people(
        session, {assessment.requested_by_id, review.reviewed_by_id if review else None}
    )
    return _out(
        assessment,
        review,
        people,
        notes=may_see_notes(rel),
        current=service.current_inputs(session, run),
    )


@router.put(
    "/cases/{case_id}/analysis-runs/{run_id}/assessments/{assessment_id}/review",
    response_model=AssessmentReviewOut,
    responses=problem_responses(403, 404, 409, 422),
)
def review_assessment(
    case_id: str,
    run_id: str,
    assessment_id: str,
    body: AssessmentReviewIn,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    settings: Settings = Depends(get_settings),
) -> AssessmentReviewOut:
    """Accept, edit (the summary, in the lawyer's wording), reject or clear one
    ready assessment. The assessment itself is never changed."""
    case, _ = authz.load_case(
        session, user, case_service.parse_case_id(case_id), Action.REVIEW_ASSESSMENT, audit
    )
    run = _ready_run(session, case, run_id)
    assessment = _assessment(session, run, assessment_id)
    if assessment.status != "ready" or assessment.result is None:
        raise ProblemError(409, "assessment-not-reviewable", NOT_REVIEWABLE)
    if body.status == "edited":
        wording = (body.reviewed_text or "").strip()
        if not wording:
            raise ProblemError(
                422, "reviewed-text-required", "Enter the wording you accept for the summary."
            )
        original = str(assessment.result.get("summary") or "")
        if " ".join(wording.split()) == " ".join(original.split()):
            raise ProblemError(
                422,
                "wording-unchanged",
                "The wording is unchanged from the assessment's; accept it instead.",
            )
    elif body.reviewed_text is not None:
        raise ProblemError(
            422,
            "reviewed-text-not-allowed",
            "Only an edited assessment has the lawyer's own wording.",
        )
    change = finding_reviews.normalised(body.status, body.reviewed_text, body.note)
    try:
        with session.begin_nested():
            outcome = service.apply_review(
                session,
                assessment,
                change,
                expected_version=body.expected_version,
                actor_id=user.id,
                now=_now(),
            )
    except service.StaleVersionError as stale:
        raise ProblemError(
            409,
            "review-changed",
            "This assessment was reviewed again in the meantime "
            f"(now version {stale.current_version}). Reload it and try again.",
        ) from None
    except IntegrityError:
        raise ProblemError(
            409,
            "review-changed",
            "This assessment was reviewed again in the meantime. Reload it and try again.",
        ) from None
    session.commit()
    if outcome.changed and outcome.review is not None:
        audit.record(
            "assessment.reviewed",
            actor=user,
            target_type="analysis_run",
            target_id=run.id,
            case_id=case.id,
            details={
                "assessment": str(assessment.id),
                "status": change.status,
                "version": outcome.review.version,
                "wordingChanged": outcome.wording_changed,
                "noteChanged": outcome.note_changed,
            },
        )
    return _review_out(outcome.review, _people(session, {user.id}), notes=True)


@router.get(
    "/cases/{case_id}/analysis-runs/{run_id}/assessments/{assessment_id}/review/history",
    response_model=AssessmentReviewHistoryOut,
    responses=problem_responses(404, 409),
)
def assessment_review_history(
    case_id: str,
    run_id: str,
    assessment_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    settings: Settings = Depends(get_settings),
) -> AssessmentReviewHistoryOut:
    case, rel = authz.load_case(
        session, user, case_service.parse_case_id(case_id), Action.VIEW, audit
    )
    run = _ready_run(session, case, run_id)
    assessment = _assessment(session, run, assessment_id)
    events = service.history(session, assessment.id)
    people = _people(session, {e.actor_id for e in events})
    notes = may_see_notes(rel)
    return AssessmentReviewHistoryOut(
        assessment_id=assessment.id,
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
