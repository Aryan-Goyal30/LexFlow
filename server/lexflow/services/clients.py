"""Clients: who may see them, add them and change their details.

- Seeing a client (with contact details): Administrators see every client;
  other staff see the clients of cases they may see.
- Adding a client: Administrators and Advocates (they open cases for them).
- Changing a client's details: Administrators, and Advocates who lead or work
  on one of the client's cases.

Clients are never deleted here: cases refer to them, and the record of who a
case was for must stay.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Select, exists, select
from sqlalchemy.orm import Session

from lexflow import authz, demo
from lexflow.audit import AuditLog
from lexflow.authz import Relation
from lexflow.domain import ADMINISTRATOR
from lexflow.errors import ProblemError
from lexflow.models import Case, Client, User
from lexflow.schemas import ClientDetail, ClientIn, ClientOut, ClientUpdate
from lexflow.services import cases as case_service

CLIENT_NOT_FOUND = "No client with this id exists."
EDITORS = frozenset({Relation.ADMIN, Relation.LEAD, Relation.ASSOCIATE})


def not_found() -> ProblemError:
    return ProblemError(404, "client-not-found", CLIENT_NOT_FOUND)


def parse_client_id(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise not_found() from None


def _relations(session: Session, user: User, client: Client) -> set[Relation]:
    """The user's relations to each case of this client they may see."""
    if user.role == ADMINISTRATOR:
        return {Relation.ADMIN}
    cases = session.scalars(
        select(Case).where(Case.client_id == client.id, authz.visible_cases(user))
    ).all()
    return {authz.relation(session, user, case) for case in cases} - {Relation.NONE}


def _load(
    session: Session, user: User, client_id: uuid.UUID, *, lock: bool = False
) -> tuple[Client, set[Relation]]:
    client = session.get(Client, client_id, with_for_update=lock)
    if client is None:
        raise not_found()
    relations = _relations(session, user, client)
    if not relations:
        raise not_found()  # a client you cannot see is reported as missing
    return client, relations


def get_detail(session: Session, user: User, client_id: uuid.UUID, today: date) -> ClientDetail:
    client, relations = _load(session, user, client_id)
    cases = case_service.list_cases(session, today, user, "include", client_id=client.id)
    return ClientDetail.model_validate(
        {
            **ClientOut.model_validate(client).model_dump(),
            "cases": cases,
            "can_edit": bool(relations & EDITORS),
        }
    )


def create(
    session: Session,
    data: ClientIn,
    *,
    user: User,
    audit: AuditLog,
    fictional_allowed: bool = False,
) -> Client:
    """Add a client. A fictional demo client (``data.fictional``) is stored as a
    sample record, and only when the caller verified the isolated demo database
    (``fictional_allowed``, see ``lexflow/demo.py``)."""
    if data.fictional and not fictional_allowed:
        raise ProblemError(409, "demo-environment-unverified", demo.UNVERIFIED)
    client = Client(
        name=data.name,
        email=data.email,
        phone=data.phone,
        company=data.company,
        is_sample=data.fictional,
    )
    session.add(client)
    session.commit()
    audit.record(
        "client.created",
        actor=user,
        target_type="client",
        target_id=client.id,
        details={"fictional": True} if data.fictional else None,
    )
    return client


def update(
    session: Session, client_id: uuid.UUID, data: ClientUpdate, *, user: User, audit: AuditLog
) -> Client:
    client, relations = _load(session, user, client_id, lock=True)
    if not relations & EDITORS:
        audit.record(
            "client.update",
            actor=user,
            outcome="denied",
            target_type="client",
            target_id=client.id,
        )
        raise ProblemError(
            403,
            "forbidden",
            "Only an administrator, or an advocate on one of this client's cases, "
            "can change these details.",
        )
    changed = [
        name
        for name, value in data.model_dump(exclude_unset=True).items()
        if getattr(client, name) != value
    ]
    for name in changed:
        setattr(client, name, getattr(data, name))
    if changed:
        session.commit()
        audit.record(
            "client.updated",
            actor=user,
            target_type="client",
            target_id=client.id,
            details={"fields": changed},
        )
    return client


def visible_query(user: User) -> Select[tuple[Client]]:
    """Clients ``user`` may see, by name."""
    query = select(Client).order_by(Client.name, Client.id)
    if user.role != ADMINISTRATOR:
        query = query.where(
            exists(select(Case.id).where(Case.client_id == Client.id, authz.visible_cases(user)))
        )
    return query
