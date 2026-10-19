"""The audit log: who did what to which record, and whether it was allowed.

Events are written through an *independent* session that commits on its own
(``lexflow.db.get_independent_sessions``):

- for an action that succeeded, the caller records the event only after its
  own transaction committed, so the log never claims a change that was rolled
  back;
- for a refused or failed action (a wrong password, access to another
  client's case), the event is kept even though the request fails.

What the log does not protect against: anyone holding the database owner's
credentials can disable the append-only trigger, TRUNCATE the table or edit
rows. See ``docs/adr/0014-audit-log.md``.

``details`` takes only short, non-secret values. Keys that look like secrets
are rejected outright: a caller passing one is a bug.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import Depends

from lexflow.db import IndependentSessions, get_independent_sessions
from lexflow.models import AuditEvent, User

logger = logging.getLogger("lexflow.audit")

FORBIDDEN_DETAIL_KEYS = ("password", "token", "cookie", "secret", "hash", "session")
MAX_DETAIL_TEXT = 200

DetailValue = str | int | bool | None | list[str]


class Actor:
    """Who an event is attributed to: a user, or an operator at the command line."""

    def __init__(self, user_id: uuid.UUID | None, name: str | None, role: str | None) -> None:
        self.id, self.name, self.role = user_id, name, role

    @classmethod
    def of(cls, user: User | None) -> Actor:
        if user is None:
            return cls(None, None, None)
        return cls(user.id, user.name, user.role)

    @classmethod
    def command_line(cls, operator: str) -> Actor:
        return cls(None, f"command line ({operator})", "Operator")


def clean_details(details: dict[str, DetailValue] | None) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in (details or {}).items():
        lowered = key.lower()
        if any(word in lowered for word in FORBIDDEN_DETAIL_KEYS):
            raise ValueError(f"audit details may not include {key!r}")
        if isinstance(value, str):
            value = value[:MAX_DETAIL_TEXT]
        elif isinstance(value, list):
            value = [str(v)[:MAX_DETAIL_TEXT] for v in value][:50]
        cleaned[key] = value
    return cleaned


class AuditLog:
    def __init__(self, sessions: IndependentSessions) -> None:
        self._sessions = sessions

    def record(
        self,
        action: str,
        *,
        actor: Actor | User | None,
        outcome: str = "success",
        target_type: str | None = None,
        target_id: uuid.UUID | None = None,
        case_id: uuid.UUID | None = None,
        details: dict[str, DetailValue] | None = None,
    ) -> None:
        """Write one event.

        A database failure is logged, not raised: the action has already happened
        (or failed) and the caller's answer must not change because of the log.
        Details with a secret-looking key raise ``ValueError`` (a programming error).
        """
        who = actor if isinstance(actor, Actor) else Actor.of(actor)
        event = AuditEvent(
            actor_id=who.id,
            actor_name=who.name,
            actor_role=who.role,
            action=action,
            outcome=outcome,
            target_type=target_type,
            target_id=target_id,
            case_id=case_id,
            details=clean_details(details),
        )
        try:
            with self._sessions() as session:
                session.add(event)
        except Exception as exc:  # the action itself already happened (or failed)
            logger.error("Could not write audit event %s (%s)", action, type(exc).__name__)


def get_audit_log(sessions: IndependentSessions = Depends(get_independent_sessions)) -> AuditLog:
    return AuditLog(sessions)
