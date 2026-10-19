"""Client records: details, adding and changing them (staff).

The list and the new-case choices are in ``lexflow.api.reference``.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from lexflow.audit import AuditLog, get_audit_log
from lexflow.auth.deps import require_roles, require_user
from lexflow.clock import get_today
from lexflow.db import get_session
from lexflow.domain import ADMINISTRATOR, ADVOCATE
from lexflow.errors import problem_responses
from lexflow.models import Client, User
from lexflow.schemas import ClientDetail, ClientIn, ClientOut, ClientUpdate
from lexflow.services import clients as service

router = APIRouter(tags=["clients"])


@router.get("/clients/{client_id}", response_model=ClientDetail, responses=problem_responses(404))
def get_client(
    client_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    today: date = Depends(get_today),
) -> ClientDetail:
    """A client's details and the cases of theirs you may see.

    404 for a client none of whose cases you may see (Administrators see all).
    """
    return service.get_detail(session, user, service.parse_client_id(client_id), today)


@router.post(
    "/clients",
    response_model=ClientOut,
    status_code=201,
    responses=problem_responses(403, 422),
)
def create_client(
    data: ClientIn,
    response: Response,
    user: User = Depends(require_roles(ADMINISTRATOR, ADVOCATE)),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
) -> Client:
    """Add a client (Administrators and Advocates)."""
    client = service.create(session, data, user=user, audit=audit)
    response.headers["Location"] = f"/api/clients/{client.id}"
    return client


@router.patch(
    "/clients/{client_id}",
    response_model=ClientOut,
    responses=problem_responses(403, 404, 422),
)
def update_client(
    client_id: str,
    data: ClientUpdate,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
) -> Client:
    """Change a client's details (an Administrator, or an Advocate on one of their cases)."""
    return service.update(session, service.parse_client_id(client_id), data, user=user, audit=audit)
