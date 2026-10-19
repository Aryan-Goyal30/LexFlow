"""Reference data for forms: clients and advocates."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from lexflow.db import get_session
from lexflow.models import Client, User
from lexflow.schemas import AdvocateOut, ClientOut

router = APIRouter(tags=["reference data"])


@router.get("/clients", response_model=list[ClientOut])
def list_clients(session: Session = Depends(get_session)) -> Sequence[Client]:
    """All clients, by name."""
    return session.scalars(select(Client).order_by(Client.name, Client.id)).all()


@router.get("/advocates", response_model=list[AdvocateOut])
def list_advocates(session: Session = Depends(get_session)) -> Sequence[User]:
    """Users who can lead a case (role Advocate), by name."""
    return session.scalars(
        select(User).where(User.role == "Advocate").order_by(User.name, User.id)
    ).all()
