"""Database rules for accounts, sessions and the audit log (migration 0002)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from lexflow.models import AuditEvent, Client, User, UserSession


def _client(db: Session) -> Client:
    client = Client(name="Example Client", email="contact@client.example", phone="+91 0")
    db.add(client)
    db.flush()
    return client


def _rejects(db: Session, *rows: object) -> None:
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add_all(rows)
        db.flush()


def test_client_users_must_represent_a_client(db: Session) -> None:
    _rejects(db, User(name="No Client", email="a@client.example", role="Client"))


def test_staff_cannot_be_linked_to_a_client(db: Session) -> None:
    client = _client(db)
    _rejects(db, User(name="Staff", email="s@lexflow.test", role="Advocate", client_id=client.id))


def test_a_password_needs_an_email(db: Session) -> None:
    _rejects(db, User(name="Nameless", role="Advocate", password_hash="$argon2id$x"))


def test_several_users_may_represent_one_client(db: Session) -> None:
    client = _client(db)
    db.add_all(
        [
            User(
                name="Contact One", email="one@client.example", role="Client", client_id=client.id
            ),
            User(
                name="Contact Two", email="two@client.example", role="Client", client_id=client.id
            ),
        ]
    )
    db.flush()  # no unique constraint on client_id


def test_new_users_are_active_and_unlocked_by_default(db: Session) -> None:
    user = User(name="Default", email="d@lexflow.test", role="Paralegal")
    db.add(user)
    db.flush()
    db.refresh(user)
    assert (user.is_active, user.must_change_password, user.failed_login_count) == (True, False, 0)


def test_session_tokens_are_stored_as_unique_hashes(db: Session) -> None:
    user = User(name="Signed In", email="si@lexflow.test", role="Advocate")
    db.add(user)
    db.flush()
    now = datetime.now(UTC)
    digest = hashlib.sha256(b"token").hexdigest()

    def session_row(token_hash: str) -> UserSession:
        return UserSession(
            user_id=user.id,
            token_hash=token_hash,
            last_seen_at=now,
            expires_at=now + timedelta(hours=1),
        )

    db.add(session_row(digest))
    db.flush()
    _rejects(db, session_row(digest))  # duplicate
    _rejects(db, session_row("not-a-sha256-digest"))  # a raw token would be rejected


def test_audit_events_cannot_be_updated_or_deleted(db: Session) -> None:
    event = AuditEvent(action="test.event", outcome="success", details={"field": "status"})
    db.add(event)
    db.flush()

    with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
        db.execute(
            text("UPDATE audit_events SET action = 'tampered' WHERE id = :id"), {"id": event.id}
        )
    with pytest.raises(DBAPIError, match="append-only"), db.begin_nested():
        db.execute(text("DELETE FROM audit_events WHERE id = :id"), {"id": event.id})
    assert db.get(AuditEvent, event.id) is not None


def test_audit_outcome_is_constrained(db: Session) -> None:
    _rejects(db, AuditEvent(id=uuid.uuid4(), action="test.event", outcome="maybe"))
