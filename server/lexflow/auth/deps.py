"""FastAPI dependencies that identify the signed-in user.

- ``require_session``: any live session (used by /auth/me, /auth/password and
  /auth/logout), else 401 ``not-authenticated``.
- ``require_user``: a live session whose user does not still have to replace a
  temporary password, else 403 ``password-change-required``. Every protected
  router depends on it.
- ``require_roles(...)``: additionally limits a route to some roles (403).

The user is taken only from the server-side session, never from anything the
client sends.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from lexflow.auth import sessions
from lexflow.clock import get_now
from lexflow.config import Settings, get_settings
from lexflow.db import get_session
from lexflow.errors import ProblemError
from lexflow.models import User, UserSession


@dataclass
class Principal:
    user: User
    session: UserSession


def not_authenticated() -> ProblemError:
    return ProblemError(
        401,
        "not-authenticated",
        "Sign in to continue.",
        title="Not signed in",
    )


def forbidden(detail: str = "You do not have permission to do this.") -> ProblemError:
    return ProblemError(403, "forbidden", detail)


def session_token(request: Request, settings: Settings) -> str | None:
    return request.cookies.get(settings.session_cookie_name)


def require_session(
    request: Request,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    now: datetime = Depends(get_now),
) -> Principal:
    found = sessions.find(session, session_token(request, settings), now=now, settings=settings)
    if found is None:
        raise not_authenticated()
    live, user = found
    if sessions.touch(live, now):
        session.commit()  # nothing else is pending: the route has not run yet
    return Principal(user=user, session=live)


def require_user(principal: Principal = Depends(require_session)) -> User:
    if principal.user.must_change_password:
        raise ProblemError(
            403,
            "password-change-required",
            "Choose a new password before continuing.",
        )
    return principal.user


def require_roles(*roles: str) -> Callable[[User], User]:
    allowed = frozenset(roles)

    def dependency(user: User = Depends(require_user)) -> User:
        if user.role not in allowed:
            raise forbidden()
        return user

    return dependency
