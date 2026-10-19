"""Reference data for forms: clients and advocates (staff only)."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from lexflow.auth.deps import require_roles, require_user
from lexflow.db import get_session
from lexflow.domain import ADMINISTRATOR, ADVOCATE, PARALEGAL
from lexflow.models import Client, User
from lexflow.schemas import AdvocateOut, ClientOption, ClientOut, StaffOut
from lexflow.services import clients

router = APIRouter(tags=["reference data"])


@router.get("/clients", response_model=list[ClientOut])
def list_clients(
    user: User = Depends(require_user), session: Session = Depends(get_session)
) -> Sequence[Client]:
    """Clients with their contact details, by name.

    Administrators see every client; Advocates and Paralegals only the clients
    of cases they may see.
    """
    return session.scalars(clients.visible_query(user)).all()


@router.get("/clients/options", response_model=list[ClientOption])
def client_options(
    _: User = Depends(require_roles(ADMINISTRATOR, ADVOCATE)),
    session: Session = Depends(get_session),
) -> Sequence[Client]:
    """Every client, by name, without contact details: the new-case form's choices.

    For those who may open cases (Administrators and Advocates).
    """
    return session.scalars(select(Client).order_by(Client.name, Client.id)).all()


@router.get("/staff", response_model=list[StaffOut])
def list_staff(session: Session = Depends(get_session)) -> Sequence[User]:
    """Active Advocates and Paralegals, by name: who can join a case team."""
    return session.scalars(
        select(User)
        .where(User.role.in_((ADVOCATE, PARALEGAL)), User.is_active.is_(True))
        .order_by(User.name, User.id)
    ).all()


@router.get("/advocates", response_model=list[AdvocateOut])
def list_advocates(session: Session = Depends(get_session)) -> Sequence[User]:
    """Active users who can lead a case (role Advocate), by name."""
    return session.scalars(
        select(User)
        .where(User.role == ADVOCATE, User.is_active.is_(True))
        .order_by(User.name, User.id)
    ).all()
