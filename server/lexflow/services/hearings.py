"""Scheduling, changing and cancelling hearings on a case.

Anyone on the case's staff may manage its hearings (``authz.Action.MANAGE_HEARINGS``);
nothing changes on an archived case. Hearings are never deleted: a cancelled
hearing stays on the case with its reason, but is no longer the next hearing
or an upcoming one. Each change is recorded on the case timeline and in the
audit log.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from sqlalchemy.orm import Session

from lexflow import authz
from lexflow.audit import AuditLog
from lexflow.authz import Action, Relation
from lexflow.domain import HEARING_CANCELLED
from lexflow.errors import FieldError, ProblemError
from lexflow.models import Hearing, TimelineEvent, User
from lexflow.schemas import HearingIn, HearingUpdate

PAST_DATE = "The hearing date cannot be in the past."


def _past(field: str = "date") -> ProblemError:
    return ProblemError(
        422,
        "validation-error",
        "Correct the highlighted fields and try again.",
        title="Some fields are invalid",
        errors=[FieldError(field=field, message=PAST_DATE)],
    )


def _day(value: date) -> str:
    return f"{value.day} {value:%b %Y}"


def _when(hearing: Hearing) -> str:
    at = f" at {hearing.hearing_time:%H:%M}" if hearing.hearing_time else ""
    return f"{_day(hearing.hearing_date)}{at}"


def _parse_time(value: str | None) -> time | None:
    return time.fromisoformat(value) if value else None


def _timeline(
    session: Session, hearing: Hearing, today: date, user: User, label: str, text: str
) -> None:
    session.add(
        TimelineEvent(
            case_id=hearing.case_id,
            event_date=today,
            label=label,
            description=text,
            actor_id=user.id,
        )
    )


def schedule(
    session: Session,
    case_id: uuid.UUID,
    data: HearingIn,
    *,
    today: date,
    user: User,
    audit: AuditLog,
) -> Relation:
    case, rel = authz.load_case(session, user, case_id, Action.MANAGE_HEARINGS, audit, lock=True)
    if data.date < today:
        raise _past()
    hearing = Hearing(
        case_id=case.id,
        hearing_date=data.date,
        hearing_time=_parse_time(data.time),
        court=data.court,
        purpose=data.purpose,
        created_by_id=user.id,
    )
    session.add(hearing)
    session.flush()
    _timeline(
        session,
        hearing,
        today,
        user,
        "Hearing scheduled",
        f"{hearing.purpose} on {_when(hearing)}, {hearing.court}.",
    )
    session.commit()
    audit.record(
        "hearing.scheduled",
        actor=user,
        target_type="hearing",
        target_id=hearing.id,
        case_id=case.id,
        details={"date": hearing.hearing_date.isoformat()},
    )
    return rel


def update(
    session: Session,
    hearing_id: uuid.UUID,
    data: HearingUpdate,
    *,
    today: date,
    user: User,
    audit: AuditLog,
) -> tuple[uuid.UUID, Relation]:
    hearing, case, rel = authz.load_hearing(
        session, user, hearing_id, Action.MANAGE_HEARINGS, audit, lock=True
    )
    if hearing.status == HEARING_CANCELLED:
        raise ProblemError(
            409,
            "hearing-cancelled",
            "This hearing was cancelled and cannot be changed. Schedule a new one instead.",
        )
    provided = data.model_dump(exclude_unset=True)
    changes: list[str] = []
    fields: list[str] = []

    new_date = provided.get("date")
    if new_date is not None and new_date != hearing.hearing_date:
        if new_date < today:
            raise _past()
        changes.append(f"Date moved from {_day(hearing.hearing_date)} to {_day(new_date)}.")
        hearing.hearing_date = new_date
        fields.append("date")
    if "time" in provided:
        new_time = _parse_time(provided["time"])
        if new_time != hearing.hearing_time:
            changes.append(
                f"Time set to {new_time:%H:%M}." if new_time else "Time cleared (to be notified)."
            )
            hearing.hearing_time = new_time
            fields.append("time")
    for name, label in (("court", "Court"), ("purpose", "Purpose")):
        value = provided.get(name)
        if value is not None and value != getattr(hearing, name):
            setattr(hearing, name, value)
            changes.append(f"{label} updated.")
            fields.append(name)

    if changes:
        _timeline(
            session,
            hearing,
            today,
            user,
            "Hearing updated",
            f"{hearing.purpose} ({_when(hearing)}): " + " ".join(changes),
        )
        session.commit()
        audit.record(
            "hearing.updated",
            actor=user,
            target_type="hearing",
            target_id=hearing.id,
            case_id=case.id,
            details={"fields": fields},
        )
    return case.id, rel


def cancel(
    session: Session,
    hearing_id: uuid.UUID,
    reason: str | None,
    *,
    today: date,
    now: datetime,
    user: User,
    audit: AuditLog,
) -> tuple[uuid.UUID, Relation]:
    """Cancel a hearing (kept on the case). Cancelling it again changes nothing."""
    hearing, case, rel = authz.load_hearing(
        session, user, hearing_id, Action.MANAGE_HEARINGS, audit, lock=True
    )
    if hearing.status == HEARING_CANCELLED:
        return case.id, rel
    hearing.status = HEARING_CANCELLED
    hearing.cancelled_at, hearing.cancelled_by_id = now, user.id
    hearing.cancellation_reason = reason
    because = f" Reason: {reason}" if reason else ""
    _timeline(
        session,
        hearing,
        today,
        user,
        "Hearing cancelled",
        f"{hearing.purpose} on {_when(hearing)} was cancelled.{because}",
    )
    session.commit()
    audit.record(
        "hearing.cancelled",
        actor=user,
        target_type="hearing",
        target_id=hearing.id,
        case_id=case.id,
        details={"date": hearing.hearing_date.isoformat()},
    )
    return case.id, rel


def parse_hearing_id(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise ProblemError(404, "hearing-not-found", authz.HEARING_NOT_FOUND) from None
