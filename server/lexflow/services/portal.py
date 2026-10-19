"""The client portal: what a Client account may see, and nothing more.

A Client account represents one client (``users.client_id``). It sees:

- that client's cases that are not archived, without internal details
  (summary, priority, opposing party, team, timeline);
- their scheduled hearings from today on;
- the documents an advocate has explicitly shared, and no others.

Every query below filters on the signed-in account's own ``client_id``; a case
or document of anyone else answers 404 exactly like one that does not exist.
The staff routes refuse Client accounts outright (``require_roles``).
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, aliased

from lexflow.domain import CLIENT, HEARING_SCHEDULED
from lexflow.errors import ProblemError
from lexflow.models import Case, Document, Hearing, User
from lexflow.schemas import (
    PortalCaseDetail,
    PortalCaseSummary,
    PortalDocumentOut,
    PortalHearingOut,
)
from lexflow.services.cases import next_hearing_expr
from lexflow.services.formatting import format_file_size

CASE_NOT_FOUND = "No case with this id exists."
DOCUMENT_NOT_FOUND = "No document with this id exists."


def _client_id(user: User) -> uuid.UUID:
    # require_roles(CLIENT) guards the routes; this guards the queries too.
    if user.role != CLIENT or user.client_id is None:
        raise ProblemError(403, "forbidden", "This is for client accounts.")
    return user.client_id


def _summary_query(user: User, today: date) -> Select[tuple[Case, str, date | None]]:
    lead = aliased(User)
    return (
        select(Case, lead.name, next_hearing_expr(today).label("next_hearing"))
        .join(lead, lead.id == Case.lead_advocate_id)
        .where(Case.client_id == _client_id(user), Case.archived_at.is_(None))
    )


def _summary(case: Case, lead_name: str, next_hearing: date | None) -> dict[str, object]:
    return {
        "id": case.id,
        "case_number": case.case_number,
        "title": case.title,
        "status": case.status,
        "practice_area": case.practice_area,
        "lead_attorney": lead_name,
        "court_name": case.court_name,
        "opened_on": case.opened_on,
        "next_hearing": next_hearing,
    }


def list_cases(session: Session, user: User, today: date) -> list[PortalCaseSummary]:
    rows = session.execute(
        _summary_query(user, today).order_by(Case.opened_on.desc(), Case.case_number.desc())
    ).all()
    return [PortalCaseSummary.model_validate(_summary(*row)) for row in rows]


def get_case(session: Session, user: User, case_id: uuid.UUID, today: date) -> PortalCaseDetail:
    row = session.execute(_summary_query(user, today).where(Case.id == case_id)).one_or_none()
    if row is None:
        raise ProblemError(404, "case-not-found", CASE_NOT_FOUND)
    case = row[0]
    hearings = session.scalars(
        select(Hearing)
        .where(
            Hearing.case_id == case.id,
            Hearing.status == HEARING_SCHEDULED,
            Hearing.hearing_date >= today,
        )
        .order_by(Hearing.hearing_date, Hearing.hearing_time.asc().nulls_last(), Hearing.id)
    ).all()
    documents = session.scalars(
        select(Document)
        .where(
            Document.case_id == case.id,
            Document.deleted_at.is_(None),
            Document.shared_with_client_at.is_not(None),
        )
        .order_by(Document.shared_with_client_at.desc(), Document.id)
    ).all()
    return PortalCaseDetail.model_validate(
        {
            **_summary(*row),
            "hearings": [
                PortalHearingOut(
                    date=h.hearing_date,
                    time=h.hearing_time.strftime("%H:%M") if h.hearing_time else None,
                    court=h.court,
                    purpose=h.purpose,
                )
                for h in hearings
            ],
            "documents": [
                PortalDocumentOut(
                    id=d.id,
                    name=d.name,
                    type=d.document_type,
                    size=format_file_size(d.size_bytes) if d.size_bytes else "",
                    shared_on=d.shared_with_client_at.date()
                    if d.shared_with_client_at
                    else d.uploaded_on,
                    download_url=f"/api/portal/documents/{d.id}/download",
                )
                for d in documents
            ],
        }
    )


def shared_document(session: Session, user: User, document_id: uuid.UUID) -> Document:
    """A document shared with this account's client, on a case that is not archived."""
    document = session.scalar(
        select(Document)
        .join(Case, Case.id == Document.case_id)
        .where(
            Document.id == document_id,
            Case.client_id == _client_id(user),
            Case.archived_at.is_(None),
            Document.deleted_at.is_(None),
            Document.shared_with_client_at.is_not(None),
        )
    )
    if document is None:
        raise ProblemError(404, "document-not-found", DOCUMENT_NOT_FOUND)
    return document
