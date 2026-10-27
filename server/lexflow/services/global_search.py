"""The top bar's quick search across cases, clients and documents.

A case-insensitive substring match on names and numbers only (never document
text), limited per kind. Visibility follows the lists: cases by
``authz.visible_cases``, clients by ``clients.visible_query`` (Administrators see
every client), documents only when live and on a case you may see.
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from lexflow import authz
from lexflow.models import Case, Client, Document, User
from lexflow.schemas import (
    GlobalSearchCaseOut,
    GlobalSearchClientOut,
    GlobalSearchDocumentOut,
    GlobalSearchOut,
)
from lexflow.services import clients as client_service

QUERY_MIN = 2
QUERY_MAX = 100


def _pattern(q: str) -> str:
    """A LIKE pattern for ``q`` with its wildcards taken literally."""
    escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def search(session: Session, user: User, q: str, limit: int) -> GlobalSearchOut:
    like = _pattern(q)

    cases = session.execute(
        select(Case, Client.name)
        .join(Client, Client.id == Case.client_id)
        .where(
            authz.visible_cases(user),
            or_(
                Case.case_number.ilike(like, escape="\\"),
                Case.title.ilike(like, escape="\\"),
                Case.court_name.ilike(like, escape="\\"),
                Case.opposing_party.ilike(like, escape="\\"),
            ),
        )
        .order_by(Case.archived_at.is_not(None), Case.opened_on.desc(), Case.id)
        .limit(limit)
    ).all()

    clients = session.scalars(
        client_service.visible_query(user)
        .where(
            or_(
                Client.name.ilike(like, escape="\\"),
                Client.company.ilike(like, escape="\\"),
                Client.email.ilike(like, escape="\\"),
            )
        )
        .limit(limit)
    ).all()

    documents = session.execute(
        select(Document, Case.case_number, Case.title)
        .join(Case, Case.id == Document.case_id)
        .where(
            Document.deleted_at.is_(None),
            authz.visible_cases(user),
            Document.name.ilike(like, escape="\\"),
        )
        .order_by(Document.uploaded_on.desc(), Document.name, Document.id)
        .limit(limit)
    ).all()

    return GlobalSearchOut(
        cases=[
            GlobalSearchCaseOut(
                id=c.id,
                case_number=c.case_number,
                title=c.title,
                client_name=client_name,
                archived=c.archived_at is not None,
            )
            for c, client_name in cases
        ],
        clients=[GlobalSearchClientOut(id=c.id, name=c.name, company=c.company) for c in clients],
        documents=[
            GlobalSearchDocumentOut(
                id=d.id, name=d.name, case_id=d.case_id, case_number=number, case_title=title
            )
            for d, number, title in documents
        ],
    )
