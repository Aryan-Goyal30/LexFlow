"""Reading the audit log (Administrators only), newest first, a page at a time.

The log is append-only in the database (a trigger rejects UPDATE and DELETE,
migration 0002). That makes accidental or casual changes impossible through
the application, but it is not tamper-proof: someone with database
administrator rights can disable the trigger.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from lexflow.errors import FieldError, ProblemError
from lexflow.models import AuditEvent, Case
from lexflow.schemas import AuditEventOut, AuditPage


def _invalid(field: str, message: str) -> ProblemError:
    return ProblemError(
        422,
        "validation-error",
        "Correct the highlighted fields and try again.",
        title="Some fields are invalid",
        errors=[FieldError(field=field, message=message)],
    )


def read_page(
    session: Session,
    *,
    tz: ZoneInfo,
    action: str | None,
    outcome: str | None,
    actor_id: uuid.UUID | None,
    case_id: uuid.UUID | None,
    start: date | None,
    end: date | None,
    before: uuid.UUID | None,
    limit: int,
) -> AuditPage:
    """Events matching every filter given, newest first.

    ``action`` matches exactly, or as a prefix when it ends with a dot
    (``document.`` for every document event). Dates are whole days in the
    firm's time zone. ``before`` is the id of the last event of the previous
    page.
    """
    if start and end and end < start:
        raise _invalid("to", "The end date must be on or after the start date.")
    query = select(AuditEvent, Case.case_number).outerjoin(Case, Case.id == AuditEvent.case_id)
    if action:
        query = query.where(
            AuditEvent.action.startswith(action, autoescape=True)
            if action.endswith(".")
            else AuditEvent.action == action
        )
    if outcome:
        query = query.where(AuditEvent.outcome == outcome)
    if actor_id:
        query = query.where(AuditEvent.actor_id == actor_id)
    if case_id:
        query = query.where(AuditEvent.case_id == case_id)
    if start:
        query = query.where(AuditEvent.occurred_at >= datetime.combine(start, time(), tz))
    if end:
        next_day = datetime.combine(end + timedelta(days=1), time(), tz)
        query = query.where(AuditEvent.occurred_at < next_day)
    if before:
        cursor = session.get(AuditEvent, before)
        if cursor is None:
            raise _invalid("before", "This page of the audit log is no longer available.")
        query = query.where(
            or_(
                AuditEvent.occurred_at < cursor.occurred_at,
                and_(AuditEvent.occurred_at == cursor.occurred_at, AuditEvent.id < cursor.id),
            )
        )
    rows = session.execute(
        query.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc()).limit(limit + 1)
    ).all()
    events = [
        AuditEventOut.model_validate(
            {
                "id": e.id,
                "occurred_at": e.occurred_at,
                "actor_id": e.actor_id,
                "actor_name": e.actor_name,
                "actor_role": e.actor_role,
                "action": e.action,
                "outcome": e.outcome,
                "target_type": e.target_type,
                "target_id": e.target_id,
                "case_id": e.case_id,
                "case_number": case_number,
                "details": e.details,
            }
        )
        for e, case_number in rows[:limit]
    ]
    more = len(rows) > limit
    return AuditPage(events=events, next_before=events[-1].id if more and events else None)
