"""Sign-in bookkeeping with real transactions (no test-transaction overrides).

Ordinary tests run every request inside one rolled-back test transaction, which
would hide a bug where a failure counter or an audit entry is written in the
request's own transaction and then lost when the request fails. These tests use
the application exactly as deployed: each request has its own session and the
audit/lockout writes use their own, independently committed sessions.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from lexflow.auth.passwords import hash_password
from lexflow.models import AuditEvent, User, UserSession
from tests.conftest import TEST_PASSWORD, http_client


@pytest.fixture
def real_app(committed_engine: Engine) -> FastAPI:
    from lexflow.main import create_app

    return create_app()  # no dependency overrides


def committed_user(engine: Engine) -> uuid.UUID:
    with Session(engine) as session, session.begin():
        user = User(
            name="Committed Advocate",
            email="committed@lexflow.test",
            role="Advocate",
            password_hash=hash_password(TEST_PASSWORD, "test-fast"),
        )
        session.add(user)
        session.flush()
        return user.id


def test_failures_and_lockout_survive_the_failed_requests(
    committed_engine: Engine, real_app: FastAPI
) -> None:
    user_id = committed_user(committed_engine)
    with http_client(real_app, raise_server_exceptions=False) as http:
        for _ in range(5):
            response = http.post(
                "/api/auth/login", json={"email": "committed@lexflow.test", "password": "wrong"}
            )
            assert response.status_code == 401

    with Session(committed_engine) as session:  # a fresh connection sees only committed data
        user = session.get(User, user_id)
        assert user is not None
        assert user.failed_login_count == 5
        assert user.locked_until is not None
        # In the order they happened: without ORDER BY the database may return
        # them in any order (this test failed intermittently because of that).
        events = session.scalars(
            select(AuditEvent)
            .where(AuditEvent.action == "auth.sign_in")
            .order_by(AuditEvent.occurred_at, AuditEvent.id)
        ).all()
        assert [e.outcome for e in events] == ["failed"] * 5
        assert [e.details.get("locked") for e in events] == [False] * 4 + [True]


def test_a_sign_in_that_rolls_back_is_not_audited_as_a_success(
    committed_engine: Engine, real_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = committed_user(committed_engine)

    def fail(*_: object, **__: object) -> None:
        raise RuntimeError("storage failure while signing in")

    monkeypatch.setattr("lexflow.auth.service.sessions.purge_stale", fail)
    with http_client(real_app, raise_server_exceptions=False) as http:
        response = http.post(
            "/api/auth/login", json={"email": "committed@lexflow.test", "password": TEST_PASSWORD}
        )
    assert response.status_code == 500
    assert "set-cookie" not in response.headers

    with Session(committed_engine) as session:
        assert (
            session.scalars(select(UserSession).where(UserSession.user_id == user_id)).all() == []
        )
        outcomes = session.scalars(
            select(AuditEvent.outcome).where(AuditEvent.action == "auth.sign_in")
        ).all()
        assert "success" not in outcomes
        user = session.get(User, user_id)
        assert user is not None and user.last_login_at is None  # the sign-in did not happen
