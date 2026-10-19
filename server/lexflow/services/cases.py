"""Reading, creating and updating cases."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.orm import Session, aliased, selectinload

from lexflow.errors import FieldError, ProblemError
from lexflow.models import Case, Client, Document, Hearing, TimelineEvent, User
from lexflow.schemas import (
    ActorOut,
    CaseCreate,
    CaseDetail,
    CaseSummary,
    CaseUpdate,
    DocumentOut,
    HearingOut,
    TimelineEventOut,
    UpcomingHearingOut,
)
from lexflow.services.case_numbers import allocate_case_number
from lexflow.services.formatting import format_file_size

CASE_NOT_FOUND = "No case with this id exists."
CLIENT_MESSAGE = "Select a client from the list."
ADVOCATE_MESSAGE = "Select a lead advocate from the list."
PAST_HEARING_MESSAGE = "The next hearing date cannot be in the past."

# Human-readable field names for timeline entries.
FIELD_LABELS = {
    "title": "title",
    "status": "status",
    "priority": "priority",
    "practice_area": "practice area",
    "client_id": "client",
    "lead_advocate_id": "lead advocate",
    "court_name": "court",
    "opposing_party": "opposing party",
    "description": "summary",
}


def parse_case_id(raw: str) -> uuid.UUID:
    """Ids that aren't UUIDs can't match a case: treat them as not found."""
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise ProblemError(404, "case-not-found", CASE_NOT_FOUND) from None


def next_hearing_expr(today: date) -> ColumnElement[date | None]:
    """Earliest hearing on/after today, otherwise the latest past hearing."""
    upcoming = (
        select(func.min(Hearing.hearing_date))
        .where(Hearing.case_id == Case.id, Hearing.hearing_date >= today)
        .scalar_subquery()
    )
    latest_past = (
        select(func.max(Hearing.hearing_date))
        .where(Hearing.case_id == Case.id, Hearing.hearing_date < today)
        .scalar_subquery()
    )
    return func.coalesce(upcoming, latest_past)


def _summary_query(today: date) -> Select[Any]:
    advocate = aliased(User)
    document_count = (
        select(func.count(Document.id)).where(Document.case_id == Case.id).scalar_subquery()
    )
    return (
        select(
            Case,
            Client.name.label("client_name"),
            advocate.name.label("advocate_name"),
            next_hearing_expr(today).label("next_hearing"),
            document_count.label("document_count"),
        )
        .join(Client, Client.id == Case.client_id)
        .join(advocate, advocate.id == Case.lead_advocate_id)
    )


def _summary_fields(
    case: Case,
    client_name: str,
    advocate_name: str,
    next_hearing: date | None,
    document_count: int,
) -> dict[str, Any]:
    return {
        "id": case.id,
        "case_number": case.case_number,
        "title": case.title,
        "status": case.status,
        "priority": case.priority,
        "practice_area": case.practice_area,
        "client_id": case.client_id,
        "client_name": client_name,
        "lead_advocate_id": case.lead_advocate_id,
        "lead_attorney": advocate_name,
        "court_name": case.court_name,
        "opposing_party": case.opposing_party,
        "opened_on": case.opened_on,
        "next_hearing": next_hearing,
        "document_count": document_count,
        "is_sample": case.is_sample,
    }


def list_cases(session: Session, today: date) -> list[CaseSummary]:
    rows = session.execute(
        _summary_query(today).order_by(
            Case.opened_on.desc(), Case.created_at.desc(), Case.case_number.desc()
        )
    ).all()
    return [CaseSummary.model_validate(_summary_fields(*row)) for row in rows]


def document_out(document: Document) -> DocumentOut:
    size = (
        format_file_size(document.size_bytes)
        if document.size_bytes is not None
        else document.size_label or ""
    )
    return DocumentOut(
        id=document.id,
        name=document.name,
        type=document.document_type,
        uploaded_on=document.uploaded_on,
        size=size,
        size_bytes=document.size_bytes,
        has_file=document.has_file,
        content_type=document.content_type,
        download_url=f"/api/documents/{document.id}/download" if document.has_file else None,
        is_sample=document.is_sample,
    )


def _hearing_fields(hearing: Hearing) -> dict[str, Any]:
    return {
        "id": hearing.id,
        "date": hearing.hearing_date,
        "time": hearing.hearing_time.strftime("%H:%M") if hearing.hearing_time else None,
        "court": hearing.court,
        "purpose": hearing.purpose,
        "is_sample": hearing.is_sample,
    }


def get_case_detail(session: Session, case_id: uuid.UUID, today: date) -> CaseDetail:
    row = session.execute(
        _summary_query(today)
        .where(Case.id == case_id)
        .options(
            selectinload(Case.documents),
            selectinload(Case.hearings),
            selectinload(Case.timeline),
        )
    ).one_or_none()
    if row is None:
        raise ProblemError(404, "case-not-found", CASE_NOT_FOUND)
    case = row[0]

    actor_ids = {e.actor_id for e in case.timeline if e.actor_id is not None}
    actors = (
        {u.id: u for u in session.scalars(select(User).where(User.id.in_(actor_ids)))}
        if actor_ids
        else {}
    )

    # Newest first: by upload date, then when the record was created, then name.
    documents = sorted(
        case.documents,
        key=lambda d: (
            -d.uploaded_on.toordinal(),
            -d.created_at.timestamp(),
            d.name.lower(),
            d.id,
        ),
    )
    hearings = sorted(
        case.hearings,
        key=lambda h: (h.hearing_date, h.hearing_time is None, h.hearing_time or 0, h.id),
    )
    timeline = sorted(case.timeline, key=lambda e: (e.event_date, e.created_at, e.id))

    return CaseDetail.model_validate(
        {
            **_summary_fields(*row),
            "description": case.description,
            "documents": [document_out(d) for d in documents],
            "hearings": [HearingOut.model_validate(_hearing_fields(h)) for h in hearings],
            "timeline": [
                TimelineEventOut(
                    id=e.id,
                    date=e.event_date,
                    label=e.label,
                    description=e.description,
                    actor=(
                        ActorOut(id=actors[e.actor_id].id, name=actors[e.actor_id].name)
                        if e.actor_id in actors
                        else None
                    ),
                    is_sample=e.is_sample,
                )
                for e in timeline
            ],
        }
    )


def get_case(session: Session, case_id: uuid.UUID, *, lock: bool = False) -> Case:
    """Load a case or raise 404. ``lock`` takes a row lock (SELECT ... FOR UPDATE)."""
    case = session.get(Case, case_id, with_for_update=lock)
    if case is None:
        raise ProblemError(404, "case-not-found", CASE_NOT_FOUND)
    return case


def _check_references(
    session: Session, client_id: uuid.UUID | None, advocate_id: uuid.UUID | None
) -> list[FieldError]:
    errors: list[FieldError] = []
    if client_id is not None and session.get(Client, client_id) is None:
        errors.append(FieldError(field="clientId", message=CLIENT_MESSAGE))
    if advocate_id is not None:
        advocate = session.get(User, advocate_id)
        if advocate is None or advocate.role != "Advocate":
            errors.append(FieldError(field="leadAdvocateId", message=ADVOCATE_MESSAGE))
    return errors


def _invalid(errors: Sequence[FieldError]) -> ProblemError:
    return ProblemError(
        422,
        "validation-error",
        "Correct the highlighted fields and try again.",
        title="Some fields are invalid",
        errors=errors,
    )


def create_case(session: Session, data: CaseCreate, today: date) -> uuid.UUID:
    """Create a case with its first hearing and an opening timeline entry.

    Commits. Returns the new case's id.
    """
    errors = _check_references(session, data.client_id, data.lead_advocate_id)
    if data.next_hearing is not None and data.next_hearing < today:
        errors.append(FieldError(field="nextHearing", message=PAST_HEARING_MESSAGE))
    if errors:
        raise _invalid(errors)

    case = Case(
        case_number=allocate_case_number(session, today.year),
        title=data.title,
        status=data.status,
        priority=data.priority,
        practice_area=data.practice_area,
        client_id=data.client_id,
        lead_advocate_id=data.lead_advocate_id,
        court_name=data.court_name,
        opposing_party=data.opposing_party,
        description=data.description,
        opened_on=today,
    )
    session.add(case)
    session.flush()

    if data.next_hearing is not None:
        # No time is known until the court lists the matter: stored as NULL.
        session.add(
            Hearing(
                case_id=case.id,
                hearing_date=data.next_hearing,
                hearing_time=None,
                court="To be notified",
                purpose="First listing",
            )
        )
    session.add(
        TimelineEvent(
            case_id=case.id,
            event_date=today,
            label="Matter opened",
            description="Matter created in LexFlow.",
            actor_id=None,  # no signed-in user in Phase 1
        )
    )
    session.commit()
    return case.id


def update_case(session: Session, case_id: uuid.UUID, data: CaseUpdate, today: date) -> None:
    """Apply the fields present in ``data``. Records a timeline entry if anything changed.

    Commits only when something changed.
    """
    # Lock the row so concurrent updates compare against committed values:
    # otherwise two identical PATCHes could both record "changed from X to Y".
    case = get_case(session, case_id, lock=True)
    provided = data.model_dump(exclude_unset=True)

    errors = _check_references(session, provided.get("client_id"), provided.get("lead_advocate_id"))
    if errors:
        raise _invalid(errors)

    changes: list[str] = []
    for name, value in provided.items():
        old = getattr(case, name)
        if old == value:
            continue
        if name in ("status", "priority"):
            changes.append(f"{FIELD_LABELS[name].capitalize()} changed from {old} to {value}.")
        else:
            changes.append(f"{FIELD_LABELS[name].capitalize()} updated.")
        setattr(case, name, value)

    if not changes:
        return

    session.add(
        TimelineEvent(
            case_id=case.id,
            event_date=today,
            label="Case details updated",
            description=" ".join(changes),
            actor_id=None,  # recorded by the system: no signed-in user in Phase 1
        )
    )
    session.commit()


def upcoming_hearings(session: Session, today: date, limit: int) -> list[UpcomingHearingOut]:
    rows = session.execute(
        select(Hearing, Case.title, Case.case_number)
        .join(Case, Case.id == Hearing.case_id)
        .where(Hearing.hearing_date >= today)
        .order_by(
            Hearing.hearing_date,
            Hearing.hearing_time.asc().nulls_last(),
            Case.case_number,
            Hearing.id,
        )
        .limit(limit)
    ).all()
    return [
        UpcomingHearingOut.model_validate(
            {**_hearing_fields(h), "case_id": h.case_id, "case_title": title, "case_number": number}
        )
        for h, title, number in rows
    ]
