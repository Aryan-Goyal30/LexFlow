"""Account administration from the app (Administrators only).

The same rules as ``python -m lexflow.cli.users``: no self-registration; a new
account, or a reset, gets a temporary password chosen by the administrator,
which the user must replace at the next sign-in. Passwords are never returned,
logged or audited. An account's role cannot be changed (create a new account
instead), and an Administrator can neither disable nor reset their own account
here, nor disable the last active Administrator.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from lexflow.audit import AuditLog
from lexflow.auth import passwords, sessions
from lexflow.auth.service import find_user_by_email, set_password
from lexflow.config import Settings
from lexflow.domain import ADMINISTRATOR, CLIENT
from lexflow.errors import FieldError, ProblemError
from lexflow.models import Client, User
from lexflow.schemas import AdminUserCreate, AdminUserOut, AdminUserUpdate

USER_NOT_FOUND = "No account with this id exists."


def _invalid(field: str, message: str) -> ProblemError:
    return ProblemError(
        422,
        "validation-error",
        "Correct the highlighted fields and try again.",
        title="Some fields are invalid",
        errors=[FieldError(field=field, message=message)],
    )


def _conflict(message: str) -> ProblemError:
    return ProblemError(409, "conflict", message)


def parse_user_id(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise ProblemError(404, "user-not-found", USER_NOT_FOUND) from None


def _get(session: Session, user_id: uuid.UUID, *, lock: bool = False) -> User:
    user = session.get(User, user_id, with_for_update=lock)
    if user is None:
        raise ProblemError(404, "user-not-found", USER_NOT_FOUND)
    return user


def user_out(user: User, client_name: str | None, now: datetime) -> AdminUserOut:
    return AdminUserOut.model_validate(
        {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "client_id": user.client_id,
            "client_name": client_name,
            "is_active": user.is_active,
            "is_locked": user.locked_until is not None and user.locked_until > now,
            "can_sign_in": user.password_hash is not None,
            "must_change_password": user.must_change_password,
            "last_login_at": user.last_login_at,
            "is_sample": user.is_sample,
        }
    )


def list_users(session: Session, now: datetime) -> list[AdminUserOut]:
    client = aliased(Client)
    rows = session.execute(
        select(User, client.name)
        .outerjoin(client, client.id == User.client_id)
        .order_by(User.role, User.name, User.id)
    ).all()
    return [user_out(user, client_name, now) for user, client_name in rows]


def get_user(session: Session, user_id: uuid.UUID, now: datetime) -> AdminUserOut:
    user = _get(session, user_id)
    client = session.get(Client, user.client_id) if user.client_id else None
    return user_out(user, client.name if client else None, now)


def _checked_password(password: str, *, email: str | None, name: str) -> str:
    problems = passwords.password_problems(password, email=email, name=name)
    if problems:
        raise _invalid("temporaryPassword", " ".join(problems))
    return password


def create(
    session: Session,
    data: AdminUserCreate,
    *,
    actor: User,
    audit: AuditLog,
    now: datetime,
    settings: Settings,
) -> uuid.UUID:
    if find_user_by_email(session, data.email) is not None:
        raise _invalid("email", "An account with this e-mail address already exists.")
    if data.role == CLIENT:
        if data.client_id is None:
            raise _invalid("clientId", "Choose the client this account represents.")
        if session.get(Client, data.client_id) is None:
            raise _invalid("clientId", "Choose a client from the list.")
    elif data.client_id is not None:
        raise _invalid("clientId", "Only client accounts represent a client.")
    password = _checked_password(data.temporary_password, email=data.email, name=data.name)

    user = User(name=data.name, email=data.email, role=data.role, client_id=data.client_id)
    session.add(user)
    session.flush()
    set_password(session, user, password, now=now, settings=settings, temporary=True)
    session.commit()
    audit.record(
        "user.created",
        actor=actor,
        target_type="user",
        target_id=user.id,
        details={"role": user.role, "via": "administration"},
    )
    return user.id


def update(
    session: Session,
    user_id: uuid.UUID,
    data: AdminUserUpdate,
    *,
    actor: User,
    audit: AuditLog,
) -> None:
    user = _get(session, user_id, lock=True)
    provided = data.model_dump(exclude_unset=True)
    if "email" in provided:
        other = find_user_by_email(session, provided["email"])
        if other is not None and other.id != user.id:
            raise _invalid("email", "An account with this e-mail address already exists.")
    changed = [name for name, value in provided.items() if getattr(user, name) != value]
    for name in changed:
        setattr(user, name, provided[name])
    if changed:
        session.commit()
        audit.record(
            "user.updated",
            actor=actor,
            target_type="user",
            target_id=user.id,
            details={"fields": changed},
        )


def _active_administrators(session: Session) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == ADMINISTRATOR, User.is_active.is_(True))
        )
        or 0
    )


def set_active(
    session: Session,
    user_id: uuid.UUID,
    *,
    active: bool,
    actor: User,
    audit: AuditLog,
    now: datetime,
) -> None:
    user = _get(session, user_id, lock=True)
    if user.is_active == active:
        return
    if not active:
        if user.id == actor.id:
            raise _conflict("You cannot disable your own account.")
        if user.role == ADMINISTRATOR and _active_administrators(session) <= 1:
            raise _conflict("This is the last active administrator; it cannot be disabled.")
    user.is_active = active
    if not active:
        sessions.revoke_all(session, user.id, now)
    session.commit()
    audit.record(
        "user.enabled" if active else "user.disabled",
        actor=actor,
        target_type="user",
        target_id=user.id,
    )


def unlock(session: Session, user_id: uuid.UUID, *, actor: User, audit: AuditLog) -> None:
    user = _get(session, user_id, lock=True)
    if user.failed_login_count == 0 and user.locked_until is None:
        return
    user.failed_login_count, user.locked_until = 0, None
    session.commit()
    audit.record("user.unlocked", actor=actor, target_type="user", target_id=user.id)


def reset_password(
    session: Session,
    user_id: uuid.UUID,
    temporary_password: str,
    *,
    actor: User,
    audit: AuditLog,
    now: datetime,
    settings: Settings,
) -> None:
    user = _get(session, user_id, lock=True)
    if user.id == actor.id:
        raise _conflict("Change your own password from your account page instead.")
    if user.email is None:
        raise _conflict("This person has no e-mail address, so they cannot sign in.")
    password = _checked_password(temporary_password, email=user.email, name=user.name)
    set_password(session, user, password, now=now, settings=settings, temporary=True)
    session.commit()
    audit.record(
        "user.password_set",
        actor=actor,
        target_type="user",
        target_id=user.id,
        details={"temporary": "true"},
    )
