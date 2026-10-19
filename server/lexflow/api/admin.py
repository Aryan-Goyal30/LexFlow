"""Account administration (Administrators only): list, create, edit, disable,
enable, unlock and reset accounts. See ``lexflow.services.users`` for the rules.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from lexflow.audit import AuditLog, get_audit_log
from lexflow.auth.deps import require_user
from lexflow.clock import get_now
from lexflow.config import Settings, get_settings
from lexflow.db import get_session
from lexflow.domain import AuditOutcome
from lexflow.errors import problem_responses
from lexflow.models import User
from lexflow.schemas import (
    AdminUserCreate,
    AdminUserOut,
    AdminUserUpdate,
    AuditPage,
    TemporaryPasswordIn,
)
from lexflow.services import audit_view
from lexflow.services import users as service

router = APIRouter(prefix="/admin", tags=["administration"])


@router.get("/audit", response_model=AuditPage, responses=problem_responses(422))
def read_audit_log(
    action: str | None = Query(
        default=None,
        max_length=100,
        description="An action, or a prefix ending in a dot (``document.``).",
    ),
    outcome: AuditOutcome | None = None,
    actor_id: uuid.UUID | None = Query(default=None, alias="actorId"),
    case_id: uuid.UUID | None = Query(default=None, alias="caseId"),
    start: date | None = Query(default=None, alias="from"),
    end: date | None = Query(default=None, alias="to"),
    before: uuid.UUID | None = Query(default=None, description="``nextBefore`` of a page."),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AuditPage:
    """The audit log, newest first, filtered and a page at a time (read-only).

    Append-only in the database, but not tamper-proof against someone with
    database administrator rights.
    """
    return audit_view.read_page(
        session,
        tz=settings.tz,
        action=action,
        outcome=outcome,
        actor_id=actor_id,
        case_id=case_id,
        start=start,
        end=end,
        before=before,
        limit=limit,
    )


@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    session: Session = Depends(get_session), now: datetime = Depends(get_now)
) -> list[AdminUserOut]:
    """Every account, by role and name."""
    return service.list_users(session, now)


@router.post(
    "/users", response_model=AdminUserOut, status_code=201, responses=problem_responses(422)
)
def create_user(
    data: AdminUserCreate,
    response: Response,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    now: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings),
) -> AdminUserOut:
    """Create an account with a temporary password (replaced at first sign-in).

    The password is never returned. Client accounts need ``clientId``.
    """
    created = service.create(session, data, actor=user, audit=audit, now=now, settings=settings)
    response.headers["Location"] = f"/api/admin/users/{created}"
    return service.get_user(session, created, now)


@router.patch(
    "/users/{user_id}", response_model=AdminUserOut, responses=problem_responses(404, 422)
)
def update_user(
    user_id: str,
    data: AdminUserUpdate,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    now: datetime = Depends(get_now),
) -> AdminUserOut:
    """Change an account's name or e-mail address."""
    parsed = service.parse_user_id(user_id)
    service.update(session, parsed, data, actor=user, audit=audit)
    return service.get_user(session, parsed, now)


@router.post(
    "/users/{user_id}/disable", response_model=AdminUserOut, responses=problem_responses(404, 409)
)
def disable_user(
    user_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    now: datetime = Depends(get_now),
) -> AdminUserOut:
    """Stop an account from signing in and end its sessions.

    409 for your own account or the last active Administrator.
    """
    parsed = service.parse_user_id(user_id)
    service.set_active(session, parsed, active=False, actor=user, audit=audit, now=now)
    return service.get_user(session, parsed, now)


@router.post(
    "/users/{user_id}/enable", response_model=AdminUserOut, responses=problem_responses(404)
)
def enable_user(
    user_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    now: datetime = Depends(get_now),
) -> AdminUserOut:
    """Allow a disabled account to sign in again."""
    parsed = service.parse_user_id(user_id)
    service.set_active(session, parsed, active=True, actor=user, audit=audit, now=now)
    return service.get_user(session, parsed, now)


@router.post(
    "/users/{user_id}/unlock", response_model=AdminUserOut, responses=problem_responses(404)
)
def unlock_user(
    user_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    now: datetime = Depends(get_now),
) -> AdminUserOut:
    """Clear a lockout after repeated failed sign-ins."""
    parsed = service.parse_user_id(user_id)
    service.unlock(session, parsed, actor=user, audit=audit)
    return service.get_user(session, parsed, now)


@router.post(
    "/users/{user_id}/password",
    response_model=AdminUserOut,
    responses=problem_responses(404, 409, 422),
)
def reset_password(
    user_id: str,
    data: TemporaryPasswordIn,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    now: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings),
) -> AdminUserOut:
    """Give an account a temporary password: their sessions end, and they must
    choose a new password at the next sign-in. Not for your own account (409)."""
    parsed = service.parse_user_id(user_id)
    service.reset_password(
        session,
        parsed,
        data.temporary_password,
        actor=user,
        audit=audit,
        now=now,
        settings=settings,
    )
    return service.get_user(session, parsed, now)
