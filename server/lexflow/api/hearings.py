"""Hearings: the firm-wide schedule, and scheduling, changing and cancelling them.

The schedule covers the cases the user may see. Changes are for staff on the
case, and answer with the updated case, as the case routes do.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from lexflow.audit import AuditLog, get_audit_log
from lexflow.auth.deps import require_user
from lexflow.clock import get_now, get_today
from lexflow.db import get_session
from lexflow.errors import FieldError, ProblemError, problem_responses
from lexflow.models import User
from lexflow.schemas import (
    CaseDetail,
    HearingCancelIn,
    HearingIn,
    HearingSchedule,
    HearingUpdate,
)
from lexflow.services import cases as case_service
from lexflow.services import hearings as service

router = APIRouter(tags=["hearings"])

MAX_RANGE_DAYS = 366


@router.get(
    "/hearings",
    response_model=HearingSchedule,
    responses=problem_responses(422),
)
def hearing_schedule(
    start: date | None = Query(
        default=None, alias="from", description="First day (default: today)."
    ),
    end: date | None = Query(
        default=None, alias="to", description="Last day (default: 30 days after the first)."
    ),
    include_cancelled: bool = Query(default=False, alias="includeCancelled"),
    limit: int = Query(default=200, ge=1, le=500),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    today: date = Depends(get_today),
) -> HearingSchedule:
    """Hearings across the cases you may see, in a date range, soonest first.

    Archived cases are left out; cancelled hearings only when asked for. The
    range may span at most a year.
    """
    first = start or today
    last = end or first + timedelta(days=30)
    if last < first:
        raise _range_problem("to", "The end date must be on or after the start date.")
    if (last - first).days > MAX_RANGE_DAYS:
        raise _range_problem("to", "Choose a range of at most a year.")
    return case_service.hearing_schedule(
        session,
        user,
        start=first,
        end=last,
        include_cancelled=include_cancelled,
        limit=limit,
    )


def _range_problem(field: str, message: str) -> ProblemError:
    return ProblemError(
        422,
        "validation-error",
        "Correct the highlighted fields and try again.",
        title="Some fields are invalid",
        errors=[FieldError(field=field, message=message)],
    )


@router.post(
    "/cases/{case_id}/hearings",
    response_model=CaseDetail,
    status_code=201,
    responses=problem_responses(403, 404, 409, 422),
)
def schedule_hearing(
    case_id: str,
    data: HearingIn,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    today: date = Depends(get_today),
) -> CaseDetail:
    """Schedule a hearing on a case. The date cannot be in the past."""
    parsed = case_service.parse_case_id(case_id)
    rel = service.schedule(session, parsed, data, today=today, user=user, audit=audit)
    return case_service.get_case_detail(session, parsed, today, rel)


@router.patch(
    "/hearings/{hearing_id}",
    response_model=CaseDetail,
    responses=problem_responses(403, 404, 409, 422),
)
def update_hearing(
    hearing_id: str,
    data: HearingUpdate,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    today: date = Depends(get_today),
) -> CaseDetail:
    """Change a scheduled hearing. 409 ``hearing-cancelled`` once it is cancelled."""
    case_id, rel = service.update(
        session, service.parse_hearing_id(hearing_id), data, today=today, user=user, audit=audit
    )
    return case_service.get_case_detail(session, case_id, today, rel)


@router.post(
    "/hearings/{hearing_id}/cancel",
    response_model=CaseDetail,
    responses=problem_responses(403, 404, 409, 422),
)
def cancel_hearing(
    hearing_id: str,
    data: HearingCancelIn,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    today: date = Depends(get_today),
    now: datetime = Depends(get_now),
) -> CaseDetail:
    """Cancel a hearing. It stays on the case, with the reason if one is given."""
    case_id, rel = service.cancel(
        session,
        service.parse_hearing_id(hearing_id),
        data.reason,
        today=today,
        now=now,
        user=user,
        audit=audit,
    )
    return case_service.get_case_detail(session, case_id, today, rel)
