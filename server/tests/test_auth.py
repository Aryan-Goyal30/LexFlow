"""Signing in and out, sessions, lockout and password changes."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lexflow.auth import passwords
from lexflow.auth.sessions import token_digest
from lexflow.clock import get_now
from lexflow.config import Settings, get_settings
from lexflow.models import AuditEvent, Client, User, UserSession
from tests.conftest import APP_HEADERS, TEST_PASSWORD, http_client, make_user, sign_in

GENERIC = {
    "type": "https://lexflow.invalid/problems/invalid-credentials",
    "title": "Sign-in failed",
    "status": 401,
    "detail": "Email or password is incorrect.",
    "code": "invalid-credentials",
    "errors": [],
}


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 14, 6, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)


@pytest.fixture
def client(anon_client: TestClient) -> TestClient:
    """These tests sign in themselves: start anonymous."""
    return anon_client


@pytest.fixture
def clock(app: FastAPI) -> Clock:
    fixed = Clock()
    app.dependency_overrides[get_now] = fixed
    return fixed


@pytest.fixture
def advocate(db: Session) -> User:
    user: User = make_user(db, role="Advocate", email="advocate@lexflow.test", name="Asha Rao")
    return user


def login(http: TestClient, email: str, password: str) -> Any:
    return http.post("/api/auth/login", json={"email": email, "password": password})


def audit(db: Session, action: str) -> list[AuditEvent]:
    return list(
        db.scalars(
            select(AuditEvent).where(AuditEvent.action == action).order_by(AuditEvent.occurred_at)
        )
    )


# --- signing in ---------------------------------------------------------------------


def test_sign_in_sets_a_strict_http_only_session_cookie(
    client: TestClient, db: Session, advocate: User, clock: Clock
) -> None:
    response = login(client, "Advocate@LexFlow.test ", TEST_PASSWORD)  # case and spaces ignored

    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": str(advocate.id),
        "name": "Asha Rao",
        "email": "advocate@lexflow.test",
        "role": "Advocate",
        "clientId": None,
        "mustChangePassword": False,
    }
    assert response.headers["cache-control"] == "no-store"
    cookie = response.headers["set-cookie"]
    token = client.cookies["lexflow_session"]
    assert cookie.startswith("lexflow_session=")
    attributes = {part.strip().lower() for part in cookie.split(";")[1:]}
    assert {"httponly", "samesite=strict", "path=/"} <= attributes
    assert not any(
        a.startswith(("max-age", "expires")) for a in attributes
    )  # browser-session cookie
    assert "secure" not in attributes  # plain http://localhost in development
    # The token is long and random, never in the body, and stored only as a hash.
    assert len(token) == 43 and token not in response.text
    stored = db.scalars(select(UserSession.token_hash).where(UserSession.user_id == advocate.id))
    assert list(stored) == [token_digest(token)]

    me = client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["email"] == "advocate@lexflow.test"
    assert audit(db, "auth.sign_in")[-1].outcome == "success"


def test_secure_cookie_with_host_prefix_when_configured(
    db: Session, advocate: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lexflow.db import get_independent_sessions, get_session
    from lexflow.main import create_app
    from tests.conftest import shared_sessions

    monkeypatch.setenv("LEXFLOW_COOKIE_SECURE", "true")
    get_settings.cache_clear()
    try:
        app = create_app()
        app.dependency_overrides[get_session] = lambda: db
        app.dependency_overrides[get_independent_sessions] = lambda: shared_sessions(db)
        with TestClient(app, base_url="https://testserver", headers=APP_HEADERS) as http:
            response = login(http, advocate.email or "", TEST_PASSWORD)
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200, response.text
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("__Host-lexflow_session=")
    assert "secure" in cookie.lower()


@pytest.mark.parametrize(
    "case",
    ["unknown", "wrong-password", "inactive", "no-password", "locked"],
)
def test_every_refusal_looks_the_same(
    client: TestClient, db: Session, clock: Clock, case: str
) -> None:
    email, password = "someone@lexflow.test", TEST_PASSWORD
    if case == "wrong-password":
        make_user(db, role="Advocate", email=email)
        password = "not the right password"
    elif case == "inactive":
        make_user(db, role="Advocate", email=email, is_active=False)
    elif case == "no-password":
        make_user(db, role="Advocate", email=email, password=None)
    elif case == "locked":
        make_user(db, role="Advocate", email=email, locked_until=clock.now + timedelta(minutes=5))

    response = login(client, email, password)

    assert response.status_code == 401
    assert response.json() == GENERIC
    assert "set-cookie" not in response.headers
    reasons = [e.details.get("reason") for e in audit(db, "auth.sign_in")]
    expected = {
        "unknown": "unknown-account",
        "wrong-password": "wrong-password",
        "inactive": "inactive",
        "no-password": "no-password",
        "locked": "locked",
    }[case]
    assert reasons == [expected]


def test_paralegals_may_sign_in_now_that_their_access_is_scoped(
    client: TestClient, db: Session, clock: Clock
) -> None:
    user = make_user(db, role="Paralegal")
    response = login(client, user.email, TEST_PASSWORD)
    assert response.status_code == 200
    assert response.json()["role"] == "Paralegal"


def test_clients_may_sign_in_now_that_the_portal_isolates_them(
    client: TestClient, db: Session, clock: Clock
) -> None:
    # Enabled only after tests/test_portal.py proved the isolation.
    client_row = Client(name="A Client", email="c@client.example", phone="+91 00000 00000")
    db.add(client_row)
    db.flush()
    user = make_user(db, role="Client", client_id=client_row.id)
    response = login(client, user.email, TEST_PASSWORD)
    assert response.status_code == 200
    assert (response.json()["role"], response.json()["clientId"]) == ("Client", str(client_row.id))
    assert client.get("/api/portal/cases").status_code == 200
    assert client.get("/api/cases").status_code == 403


def test_unknown_accounts_are_not_recorded_by_address(client: TestClient, db: Session) -> None:
    login(client, "typed-a-password-here@lexflow.test", "x")
    (event,) = audit(db, "auth.sign_in")
    assert event.actor_id is None
    assert "typed-a-password-here" not in str(event.details)


# --- lockout: the 5th consecutive failure locks; the 6th attempt is refused ---------


def test_four_failures_then_the_right_password_signs_in(
    client: TestClient, db: Session, advocate: User, clock: Clock
) -> None:
    for _ in range(4):
        assert login(client, "advocate@lexflow.test", "wrong").status_code == 401
    assert login(client, "advocate@lexflow.test", TEST_PASSWORD).status_code == 200
    db.refresh(advocate)
    assert (advocate.failed_login_count, advocate.locked_until) == (0, None)


def test_five_failures_lock_the_account_for_fifteen_minutes(
    client: TestClient, db: Session, advocate: User, clock: Clock
) -> None:
    for _ in range(5):
        assert login(client, "advocate@lexflow.test", "wrong").status_code == 401
    db.refresh(advocate)
    assert advocate.locked_until == clock.now + timedelta(minutes=15)

    # The 6th attempt, even with the right password, is refused the same way.
    sixth = login(client, "advocate@lexflow.test", TEST_PASSWORD)
    assert (sixth.status_code, sixth.json()) == (401, GENERIC)

    # Attempts during the lock neither count nor extend it.
    clock.advance(minutes=10)
    login(client, "advocate@lexflow.test", "wrong")
    db.refresh(advocate)
    assert advocate.locked_until == clock.now - timedelta(minutes=10) + timedelta(minutes=15)
    assert advocate.failed_login_count == 5

    clock.advance(minutes=6)  # 16 minutes after locking
    assert login(client, "advocate@lexflow.test", TEST_PASSWORD).status_code == 200


def test_after_a_lock_expires_the_count_starts_again(
    client: TestClient, db: Session, advocate: User, clock: Clock
) -> None:
    for _ in range(5):
        login(client, "advocate@lexflow.test", "wrong")
    clock.advance(minutes=16)

    login(client, "advocate@lexflow.test", "wrong")  # one failure, not an instant re-lock
    db.refresh(advocate)
    assert (advocate.failed_login_count, advocate.locked_until) == (1, None)
    assert login(client, "advocate@lexflow.test", TEST_PASSWORD).status_code == 200


# --- sessions: idle and absolute limits, logout, fixation ---------------------------


def test_idle_sessions_expire_after_thirty_minutes(
    client: TestClient, advocate: User, clock: Clock
) -> None:
    sign_in(client, advocate)
    clock.advance(minutes=29)
    assert client.get("/api/auth/me").status_code == 200  # activity extends the session
    clock.advance(minutes=29)
    assert client.get("/api/auth/me").status_code == 200
    clock.advance(minutes=31)
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["code"] == "not-authenticated"


def test_sessions_end_twelve_hours_after_sign_in_even_when_active(
    client: TestClient, advocate: User, clock: Clock
) -> None:
    sign_in(client, advocate)
    for _ in range(24):  # a request every 25 minutes for 10 hours
        clock.advance(minutes=25)
        assert client.get("/api/auth/me").status_code == 200
    clock.advance(hours=2)
    assert client.get("/api/auth/me").status_code == 401


def test_last_seen_is_written_at_most_once_a_minute(
    client: TestClient, db: Session, advocate: User, clock: Clock
) -> None:
    sign_in(client, advocate)
    live = db.scalars(select(UserSession).where(UserSession.user_id == advocate.id)).one()
    first = live.last_seen_at
    clock.advance(seconds=30)
    client.get("/api/auth/me")
    db.refresh(live)
    assert live.last_seen_at == first
    clock.advance(seconds=31)
    client.get("/api/auth/me")
    db.refresh(live)
    assert live.last_seen_at == clock.now


def test_logout_ends_the_session_and_a_replayed_cookie_is_refused(
    app: FastAPI, db: Session, advocate: User, clock: Clock
) -> None:
    with http_client(app, raise_server_exceptions=False) as http:
        sign_in(http, advocate)
        stolen = dict(http.cookies)
        response = http.post("/api/auth/logout")
        assert response.status_code == 204
        assert "lexflow_session=" in response.headers["set-cookie"]  # cleared
    with http_client(app, raise_server_exceptions=False, cookies=stolen) as replay:
        assert replay.get("/api/auth/me").status_code == 401
    assert audit(db, "auth.sign_out")[-1].actor_id == advocate.id


def test_logout_without_a_session_is_harmless(client: TestClient) -> None:
    assert client.post("/api/auth/logout").status_code == 204


def test_signing_in_again_ends_the_previous_session(
    client: TestClient, db: Session, advocate: User, clock: Clock
) -> None:
    sign_in(client, advocate)
    first = client.cookies["lexflow_session"]
    sign_in(client, advocate)
    second = client.cookies["lexflow_session"]
    assert first != second
    rows = {
        s.token_hash: s.revoked_at
        for s in db.scalars(select(UserSession).where(UserSession.user_id == advocate.id))
    }
    assert rows[token_digest(first)] is not None and rows[token_digest(second)] is None


def test_deactivating_a_user_ends_their_sessions(
    client: TestClient, db: Session, advocate: User, clock: Clock
) -> None:
    sign_in(client, advocate)
    advocate.is_active = False
    db.commit()
    assert client.get("/api/auth/me").status_code == 401


def test_garbage_cookies_are_rejected(client: TestClient) -> None:
    for value in ["", "x", "a" * 43 + "!", "short", "A" * 43]:
        client.cookies.set("lexflow_session", value)
        assert client.get("/api/auth/me").status_code == 401


# --- temporary passwords and changing one's password -------------------------------


def test_temporary_passwords_expire(client: TestClient, db: Session, clock: Clock) -> None:
    user = make_user(
        db,
        role="Advocate",
        email="temp@lexflow.test",
        must_change_password=True,
        temp_password_expires_at=clock.now + timedelta(hours=72),
    )
    assert login(client, user.email, TEST_PASSWORD).json()["mustChangePassword"] is True
    clock.advance(hours=73)
    response = login(client, user.email, TEST_PASSWORD)
    assert (response.status_code, response.json()) == (401, GENERIC)
    assert audit(db, "auth.sign_in")[-1].details["reason"] == "temporary-password-expired"


def test_changing_the_password_needs_the_current_one_and_ends_other_sessions(
    app: FastAPI, db: Session, advocate: User, clock: Clock
) -> None:
    new_password = "a brand new passphrase"
    with (
        http_client(app, raise_server_exceptions=False) as laptop,
        http_client(app, raise_server_exceptions=False) as phone,
    ):
        sign_in(laptop, advocate)
        sign_in(phone, advocate)
        old_cookie = laptop.cookies["lexflow_session"]

        wrong = laptop.post(
            "/api/auth/password",
            json={"currentPassword": "not it", "newPassword": new_password},
        )
        assert wrong.status_code == 422
        assert [e["field"] for e in wrong.json()["errors"]] == ["currentPassword"]
        db.refresh(advocate)
        assert advocate.failed_login_count == 1  # counts towards the lockout

        changed = laptop.post(
            "/api/auth/password",
            json={"currentPassword": TEST_PASSWORD, "newPassword": new_password},
        )
        assert changed.status_code == 200, changed.text
        assert laptop.cookies["lexflow_session"] != old_cookie  # a fresh session
        assert laptop.get("/api/auth/me").status_code == 200
        assert phone.get("/api/auth/me").status_code == 401  # other sessions ended

    with http_client(app, raise_server_exceptions=False) as fresh:
        assert login(fresh, advocate.email or "", TEST_PASSWORD).status_code == 401
        assert login(fresh, advocate.email or "", new_password).status_code == 200


@pytest.mark.parametrize(
    ("new_password", "message"),
    [
        ("short", "at least 12"),
        ("x" * 129, "at most 128"),
        ("            ", "only spaces"),
        ("advocate@lexflow.test", "e-mail address or name"),
        (TEST_PASSWORD, "different from your current"),
    ],
)
def test_weak_new_passwords_are_refused(
    client: TestClient, advocate: User, clock: Clock, new_password: str, message: str
) -> None:
    sign_in(client, advocate)
    response = client.post(
        "/api/auth/password",
        json={"currentPassword": TEST_PASSWORD, "newPassword": new_password},
    )
    assert response.status_code == 422
    (error,) = response.json()["errors"]
    assert error["field"] == "newPassword" and message in error["message"]


def test_spaces_around_a_password_are_part_of_it(
    client: TestClient, db: Session, clock: Clock
) -> None:
    user = make_user(db, role="Advocate", password="  padded passphrase  ")
    assert login(client, user.email, "padded passphrase").status_code == 401
    assert login(client, user.email, "  padded passphrase  ").status_code == 200


# --- no secrets in logs, audit details or responses --------------------------------


def test_passwords_and_tokens_never_reach_logs_or_the_audit_log(
    client: TestClient, db: Session, advocate: User, clock: Clock, caplog: pytest.LogCaptureFixture
) -> None:
    wrong, new = "Wrong-Password-Marker-91", "New-Password-Marker-4711"
    with caplog.at_level(logging.DEBUG):
        login(client, "advocate@lexflow.test", wrong)
        sign_in(client, advocate)
        token = client.cookies["lexflow_session"]
        client.post(
            "/api/auth/password", json={"currentPassword": TEST_PASSWORD, "newPassword": new}
        )
        new_token = client.cookies["lexflow_session"]
        client.post("/api/auth/logout")

    everything = caplog.text + " ".join(str(e.details) for e in db.scalars(select(AuditEvent)))
    for secret in (wrong, TEST_PASSWORD, new, token, new_token):
        assert secret not in everything
    assert (db.scalar(select(func.count()).select_from(AuditEvent)) or 0) >= 4


# --- password hashing ---------------------------------------------------------------


def test_passwords_are_hashed_with_argon2id_rfc9106_parameters() -> None:
    stored = passwords.hash_password("a long enough passphrase", "standard")
    assert stored.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
    assert passwords.verify_password(stored, "a long enough passphrase", "standard")
    assert not passwords.verify_password(stored, "a long enough passphrasE", "standard")
    assert not passwords.verify_password("not a hash", "anything", "standard")
    # A cheaper (test) hash would be upgraded at the next sign-in.
    cheap = passwords.hash_password("a long enough passphrase", "test-fast")
    assert passwords.needs_rehash(cheap, "standard")


def test_the_fast_hash_profile_is_refused_outside_tests() -> None:
    with pytest.raises(ValueError, match="only allowed in tests"):
        Settings(
            database_url="postgresql+psycopg://u@127.0.0.1:1/x",
            env="development",
            password_hash_profile="test-fast",
        )


def test_audit_details_refuse_secret_looking_keys() -> None:
    from lexflow.audit import clean_details

    for key in ("password", "newPassword", "sessionToken", "cookie", "passwordHash"):
        with pytest.raises(ValueError):
            clean_details({key: "x"})
    assert clean_details({"reason": "x" * 500})["reason"] == "x" * 200
