"""Reading, creating and updating cases.

Access rules live in ``lexflow.authz``; this module applies them: lists are
scoped to the cases the user may see, and changes are checked field by field
before anything is written.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime
from typing import Any, Literal

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.orm import Session, aliased, selectinload

from lexflow import authz
from lexflow.audit import AuditLog
from lexflow.authz import Action, Relation
from lexflow.config import get_settings
from lexflow.domain import ADMINISTRATOR, ADVOCATE, HEARING_SCHEDULED
from lexflow.errors import FieldError, ProblemError
from lexflow.models import (
    Case,
    CaseMember,
    Client,
    Document,
    DocumentExtraction,
    Hearing,
    TimelineEvent,
    User,
)
from lexflow.schemas import (
    ActorOut,
    CaseCreate,
    CaseDetail,
    CasePermissions,
    CaseSummary,
    CaseUpdate,
    DeletedDocumentOut,
    DocumentOut,
    DocumentProcessingOut,
    HearingOut,
    HearingSchedule,
    ScheduledHearingOut,
    TeamMemberOut,
    TimelineEventOut,
    UpcomingHearingOut,
)
from lexflow.services import reviews
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
        .where(
            Hearing.case_id == Case.id,
            Hearing.hearing_date >= today,
            Hearing.status == HEARING_SCHEDULED,
        )
        .scalar_subquery()
    )
    latest_past = (
        select(func.max(Hearing.hearing_date))
        .where(
            Hearing.case_id == Case.id,
            Hearing.hearing_date < today,
            Hearing.status == HEARING_SCHEDULED,
        )
        .scalar_subquery()
    )
    return func.coalesce(upcoming, latest_past)


def _summary_query(today: date) -> Select[Any]:
    advocate = aliased(User)
    document_count = (
        select(func.count(Document.id))
        .where(Document.case_id == Case.id, Document.deleted_at.is_(None))
        .scalar_subquery()
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
        "archived_at": case.archived_at,
        "is_sample": case.is_sample,
    }


ArchivedFilter = Literal["exclude", "include", "only"]


def list_cases(
    session: Session,
    today: date,
    user: User,
    archived: ArchivedFilter = "exclude",
    *,
    client_id: uuid.UUID | None = None,
) -> list[CaseSummary]:
    """The cases ``user`` may see, newest first; archived ones only if asked for."""
    query = _summary_query(today).where(authz.visible_cases(user))
    if client_id is not None:
        query = query.where(Case.client_id == client_id)
    if archived == "exclude":
        query = query.where(Case.archived_at.is_(None))
    elif archived == "only":
        query = query.where(Case.archived_at.is_not(None))
    rows = session.execute(
        query.order_by(Case.opened_on.desc(), Case.created_at.desc(), Case.case_number.desc())
    ).all()
    return [CaseSummary.model_validate(_summary_fields(*row)) for row in rows]


def users_by_id(session: Session, ids: Iterable[uuid.UUID | None]) -> dict[uuid.UUID, User]:
    """The users with these ids (``None`` ignored), for naming who did what."""
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    return {u.id: u for u in session.scalars(select(User).where(User.id.in_(wanted)))}


def actor_out(users: Mapping[uuid.UUID, User], user_id: uuid.UUID | None) -> ActorOut | None:
    user = users.get(user_id) if user_id is not None else None
    return ActorOut(id=user.id, name=user.name) if user is not None else None


def extractions_for(
    session: Session, document_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, DocumentExtraction]:
    """The processing jobs of these documents, by document id."""
    wanted = set(document_ids)
    if not wanted:
        return {}
    return {
        job.document_id: job
        for job in session.scalars(
            select(DocumentExtraction).where(DocumentExtraction.document_id.in_(wanted))
        )
    }


def processing_out(job: DocumentExtraction | None) -> DocumentProcessingOut | None:
    if job is None:
        return None
    return DocumentProcessingOut.model_validate(
        {
            "status": job.status,
            "reason_code": job.reason_code,
            "reason": job.reason,
            "page_count": job.page_count,
            "section_count": job.section_count,
            "chunk_count": job.chunk_count,
            "index_status": job.index_status,
            "updated_at": job.updated_at,
        }
    )


def _document_fields(
    document: Document,
    users: Mapping[uuid.UUID, User],
    job: DocumentExtraction | None = None,
) -> dict[str, Any]:
    size = (
        format_file_size(document.size_bytes)
        if document.size_bytes is not None
        else document.size_label or ""
    )
    return {
        "id": document.id,
        "name": document.name,
        "type": document.document_type,
        "uploaded_on": document.uploaded_on,
        "size": size,
        "size_bytes": document.size_bytes,
        "has_file": document.has_file,
        "content_type": document.content_type,
        "download_url": (f"/api/documents/{document.id}/download" if document.has_file else None),
        "uploaded_by": actor_out(users, document.uploaded_by_id),
        "shared_with_client_at": document.shared_with_client_at,
        "processing": processing_out(job),
        "is_sample": document.is_sample,
    }


def document_out(
    document: Document,
    users: Mapping[uuid.UUID, User],
    job: DocumentExtraction | None = None,
) -> DocumentOut:
    return DocumentOut.model_validate(_document_fields(document, users, job))


def deleted_document_out(
    document: Document,
    users: Mapping[uuid.UUID, User],
    job: DocumentExtraction | None = None,
) -> DeletedDocumentOut:
    return DeletedDocumentOut.model_validate(
        {
            **_document_fields(document, users, job),
            "deleted_at": document.deleted_at,
            "deleted_by": actor_out(users, document.deleted_by_id),
        }
    )


def _hearing_fields(hearing: Hearing) -> dict[str, Any]:
    return {
        "id": hearing.id,
        "date": hearing.hearing_date,
        "time": hearing.hearing_time.strftime("%H:%M") if hearing.hearing_time else None,
        "court": hearing.court,
        "purpose": hearing.purpose,
        "status": hearing.status,
        "cancellation_reason": hearing.cancellation_reason,
        "is_sample": hearing.is_sample,
    }


def _timeline(
    session: Session,
    case_id: uuid.UUID,
    events: list[TimelineEvent],
    actors: Mapping[uuid.UUID, User],
) -> list[TimelineEventOut]:
    """The case's timeline entries, with the lawyers' review decisions on AI
    findings (Phase 6) merged in. Those come from the review history, not
    from ``timeline_events``, so the analysis evidence never contains them."""
    merged = [
        TimelineEventOut(
            id=e.id,
            date=e.event_date,
            label=e.label,
            description=e.description,
            actor=actor_out(actors, e.actor_id),
            recorded_at=e.created_at,
            is_sample=e.is_sample,
        )
        for e in events
    ]
    entries = reviews.timeline_entries(session, case_id, get_settings().timezone)
    reviewers = {e.actor_id for e in entries if e.actor_id is not None} - set(actors)
    if reviewers:
        more = session.scalars(select(User).where(User.id.in_(reviewers)))
        actors = {**actors, **{u.id: u for u in more}}
    merged += [
        TimelineEventOut(
            id=e.id,
            date=e.day,
            label=e.label,
            description=e.description,
            actor=actor_out(actors, e.actor_id),
            recorded_at=e.recorded_at,
            is_sample=False,
            kind="review",
        )
        for e in entries
    ]
    return sorted(merged, key=lambda e: (e.date, e.recorded_at, str(e.id)))


def get_case_detail(session: Session, case_id: uuid.UUID, today: date, rel: Relation) -> CaseDetail:
    """One case with its documents, hearings and timeline. Callers check access."""
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

    live = [d for d in case.documents if d.deleted_at is None]
    actors = users_by_id(
        session, [e.actor_id for e in case.timeline] + [d.uploaded_by_id for d in live]
    )

    jobs = extractions_for(session, (d.id for d in live))
    # Newest first: by upload date, then when the record was created, then name.
    documents = sorted(
        live,
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
            "documents": [document_out(d, actors, jobs.get(d.id)) for d in documents],
            "hearings": [HearingOut.model_validate(_hearing_fields(h)) for h in hearings],
            "timeline": _timeline(session, case.id, timeline, actors),
            "team": team_members(session, case.id),
            "permissions": CasePermissions.model_validate(
                authz.permissions(rel, is_archived=case.archived_at is not None)
            ),
        }
    )


def team_members(session: Session, case_id: uuid.UUID) -> list[TeamMemberOut]:
    rows = session.execute(
        select(User, CaseMember.member_role)
        .join(CaseMember, CaseMember.user_id == User.id)
        .where(CaseMember.case_id == case_id)
        .order_by(User.name, User.id)
    ).all()
    return [
        TeamMemberOut.model_validate(
            {"id": u.id, "name": u.name, "role": u.role, "member_role": member_role}
        )
        for u, member_role in rows
    ]


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
        if advocate is None or advocate.role != ADVOCATE or not advocate.is_active:
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


def create_case(
    session: Session, data: CaseCreate, today: date, user: User, audit: AuditLog
) -> uuid.UUID:
    """Create a case with its first hearing and an opening timeline entry.

    Administrators choose any active advocate as lead; an Advocate opens cases
    only with themselves as lead. Commits. Returns the new case's id.
    """
    if user.role != ADMINISTRATOR and data.lead_advocate_id != user.id:
        audit.record(
            "access.denied",
            actor=user,
            outcome="denied",
            target_type="case",
            details={"action": "create", "fields": ["leadAdvocateId"]},
        )
        raise ProblemError(
            403,
            "field-not-permitted",
            "You can only open cases with yourself as the lead advocate.",
            errors=[
                FieldError(
                    field="leadAdvocateId",
                    message="You can only open cases with yourself as the lead advocate.",
                )
            ],
        )
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
                created_by_id=user.id,
            )
        )
    session.add(
        TimelineEvent(
            case_id=case.id,
            event_date=today,
            label="Matter opened",
            description="Matter created in LexFlow.",
            actor_id=user.id,
        )
    )
    session.commit()
    audit.record(
        "case.created",
        actor=user,
        target_type="case",
        target_id=case.id,
        case_id=case.id,
        details={"caseNumber": case.case_number},
    )
    return case.id


def update_case(
    session: Session,
    case_id: uuid.UUID,
    data: CaseUpdate,
    today: date,
    user: User,
    audit: AuditLog,
) -> Relation:
    """Apply the fields present in ``data``. Records a timeline entry if anything changed.

    Every field is checked against the user's relationship to the case before
    anything changes (``authz.FIELD_ACTIONS``). Commits only when something
    changed. Returns the user's relationship to the case.
    """
    # Lock the row so concurrent updates compare against committed values:
    # otherwise two identical PATCHes could both record "changed from X to Y".
    case, rel = authz.load_case(session, user, case_id, Action.VIEW, audit, lock=True)
    provided = data.model_dump(exclude_unset=True)
    authz.check_fields(audit, user, case, rel, provided)
    if provided:
        authz.check_not_archived(case, Action.EDIT_DETAILS)

    errors = _check_references(session, provided.get("client_id"), provided.get("lead_advocate_id"))
    if errors:
        raise _invalid(errors)

    changes: list[str] = []
    changed_fields: list[str] = []
    for name, value in provided.items():
        old = getattr(case, name)
        if old == value:
            continue
        changed_fields.append(name)
        if name in ("status", "priority"):
            changes.append(f"{FIELD_LABELS[name].capitalize()} changed from {old} to {value}.")
        else:
            changes.append(f"{FIELD_LABELS[name].capitalize()} updated.")
        setattr(case, name, value)

    if not changes:
        return rel

    if "lead_advocate_id" in provided:
        # The new lead leads; they are no longer also a team member.
        member = session.get(CaseMember, (case.id, case.lead_advocate_id))
        if member is not None:
            session.delete(member)
    session.add(
        TimelineEvent(
            case_id=case.id,
            event_date=today,
            label="Case details updated",
            description=" ".join(changes),
            actor_id=user.id,
        )
    )
    session.commit()
    details: dict[str, str | list[str]] = {"fields": [authz.CAMEL[name] for name in changed_fields]}
    if "status" in changed_fields:
        details["newStatus"] = str(provided["status"])
    if "priority" in changed_fields:
        details["newPriority"] = str(provided["priority"])
    audit.record(
        "case.updated",
        actor=user,
        target_type="case",
        target_id=case.id,
        case_id=case.id,
        details=dict(details),
    )
    return rel


def upcoming_hearings(
    session: Session, today: date, limit: int, user: User
) -> list[UpcomingHearingOut]:
    """Hearings on or after today, only on cases ``user`` may see."""
    rows = session.execute(
        select(Hearing, Case.title, Case.case_number)
        .join(Case, Case.id == Hearing.case_id)
        .where(
            Hearing.hearing_date >= today,
            Hearing.status == HEARING_SCHEDULED,
            Case.archived_at.is_(None),
            authz.visible_cases(user),
        )
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


def hearing_schedule(
    session: Session,
    user: User,
    *,
    start: date,
    end: date,
    include_cancelled: bool,
    limit: int,
) -> HearingSchedule:
    """Hearings from ``start`` to ``end`` (inclusive) on the cases ``user`` may see.

    Archived cases are left out. Fetches one more than ``limit`` to tell whether
    the list was cut short.
    """
    lead = aliased(User)
    query = (
        select(Hearing, Case.title, Case.case_number, lead.name)
        .join(Case, Case.id == Hearing.case_id)
        .join(lead, lead.id == Case.lead_advocate_id)
        .where(
            Hearing.hearing_date >= start,
            Hearing.hearing_date <= end,
            Case.archived_at.is_(None),
            authz.visible_cases(user),
        )
        .order_by(
            Hearing.hearing_date,
            Hearing.hearing_time.asc().nulls_last(),
            Case.case_number,
            Hearing.id,
        )
        .limit(limit + 1)
    )
    if not include_cancelled:
        query = query.where(Hearing.status == HEARING_SCHEDULED)
    rows = session.execute(query).all()
    return HearingSchedule(
        hearings=[
            ScheduledHearingOut.model_validate(
                {
                    **_hearing_fields(h),
                    "case_id": h.case_id,
                    "case_title": title,
                    "case_number": number,
                    "lead_attorney": lead_name,
                }
            )
            for h, title, number, lead_name in rows[:limit]
        ],
        truncated=len(rows) > limit,
    )


def set_archived(
    session: Session,
    case_id: uuid.UUID,
    *,
    archive: bool,
    today: date,
    now: datetime,
    user: User,
    audit: AuditLog,
) -> Relation:
    """Archive (or restore) a case: nothing is deleted. Administrators only.

    Archiving an archived case, or restoring an active one, changes nothing.
    """
    case, rel = authz.load_case(session, user, case_id, Action.ARCHIVE, audit, lock=True)
    if (case.archived_at is not None) == archive:
        return rel
    case.archived_at, case.archived_by_id = (now, user.id) if archive else (None, None)
    session.add(
        TimelineEvent(
            case_id=case.id,
            event_date=today,
            label="Case archived" if archive else "Case restored",
            description=(
                "Archived: kept in full, read-only and hidden from the case list."
                if archive
                else "Restored from the archive."
            ),
            actor_id=user.id,
        )
    )
    session.commit()
    audit.record(
        "case.archived" if archive else "case.restored",
        actor=user,
        target_type="case",
        target_id=case.id,
        case_id=case.id,
    )
    return rel
