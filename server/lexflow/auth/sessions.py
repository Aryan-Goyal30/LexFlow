"""Server-side sessions.

A session token is 32 random bytes from ``secrets`` (256 bits), URL-safe base64
encoded. The browser keeps it in an HttpOnly cookie; the database keeps only its
SHA-256, so the ``sessions`` table cannot be replayed if it leaks. A session
ends when it is revoked, ``session_absolute_hours`` after sign-in, or after
``session_idle_minutes`` without a request.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from lexflow.config import Settings
from lexflow.models import User, UserSession

TOKEN_BYTES = 32
# token_urlsafe(32) gives 43 characters from the URL-safe alphabet.
TOKEN_SHAPE = re.compile(r"^[A-Za-z0-9_-]{43}$")
# last_seen_at is written at most this often, not on every request.
TOUCH_INTERVAL = timedelta(minutes=1)
USER_AGENT_MAX = 200


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def looks_like_token(value: str | None) -> bool:
    return value is not None and TOKEN_SHAPE.fullmatch(value) is not None


def start(
    session: Session,
    user: User,
    *,
    now: datetime,
    settings: Settings,
    user_agent: str | None,
) -> str:
    """Add a new session for ``user`` and return its token. The caller commits."""
    token = new_token()
    session.add(
        UserSession(
            user_id=user.id,
            token_hash=token_digest(token),
            last_seen_at=now,
            expires_at=now + timedelta(hours=settings.session_absolute_hours),
            user_agent=(user_agent or "")[:USER_AGENT_MAX] or None,
        )
    )
    return token


def find(
    session: Session, token: str | None, *, now: datetime, settings: Settings
) -> tuple[UserSession, User] | None:
    """The live session for ``token`` and its user, or None.

    Expired, idle, revoked and malformed tokens all give None, as does a session
    whose user has been deactivated.
    """
    if token is None or TOKEN_SHAPE.fullmatch(token) is None:
        return None
    row = session.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(UserSession.token_hash == token_digest(token))
    ).one_or_none()
    if row is None:
        return None
    live, user = row
    idle_limit = live.last_seen_at + timedelta(minutes=settings.session_idle_minutes)
    if live.revoked_at is not None or now >= live.expires_at or now >= idle_limit:
        return None
    if not user.is_active:
        return None
    return live, user


def touch(live: UserSession, now: datetime) -> bool:
    """Record activity (at most once a minute). True if the row changed."""
    if now - live.last_seen_at >= TOUCH_INTERVAL:
        live.last_seen_at = now
        return True
    return False


def revoke(live: UserSession, now: datetime) -> None:
    if live.revoked_at is None:
        live.revoked_at = now


def revoke_all(
    session: Session, user_id: uuid.UUID, now: datetime, *, keep: uuid.UUID | None = None
) -> None:
    """End every session of a user (password change, deactivation, role change)."""
    statement = (
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    if keep is not None:
        statement = statement.where(UserSession.id != keep)
    session.execute(statement)


def purge_stale(session: Session, now: datetime) -> None:
    """Delete sessions that ended more than a day ago, so the table stays small."""
    cutoff = now - timedelta(days=1)
    session.execute(
        delete(UserSession).where(
            or_(UserSession.expires_at < cutoff, UserSession.revoked_at < cutoff)
        )
    )
