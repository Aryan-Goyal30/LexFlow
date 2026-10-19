"""Shared test fixtures.

Tests run against a real PostgreSQL database named by ``TEST_DATABASE_URL``
(never ``DATABASE_URL``). The database is dropped and recreated at the start of
each session and migrated to ``head`` with Alembic, so the schema under test is
the one the migrations produce.

Each test runs inside a transaction that is rolled back afterwards. Tests that
need real commits (for example concurrent case creation) use ``committed_engine``
and clean up after themselves.
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from dotenv import dotenv_values
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import URL, Connection, Engine, create_engine, make_url, text
from sqlalchemy.orm import Session

SERVER_ROOT = Path(__file__).resolve().parent.parent

# Shared fixtures for the access-rule tests (people in roles around one case).
pytest_plugins = ["tests.access_fixtures"]


def _test_database_url() -> URL:
    raw = os.environ.get("TEST_DATABASE_URL") or dotenv_values(SERVER_ROOT / ".env").get(
        "TEST_DATABASE_URL"
    )
    if not raw:
        pytest.exit("TEST_DATABASE_URL is not set (see server/.env.example)", returncode=2)
    url = make_url(raw)
    if "test" not in (url.database or ""):
        # Guard against pointing the destructive test setup at a real database.
        pytest.exit(f"Refusing to use database {url.database!r}: its name must contain 'test'", 2)
    return url


# Connection details are passed around as sqlalchemy URL objects, never plain
# strings: a URL's repr masks the password, so it can't leak into test output.
TEST_DATABASE_URL: URL = _test_database_url()

# The app reads its settings from the environment; point it at the test database
# before anything imports lexflow.config.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL.render_as_string(hide_password=False)
os.environ["LEXFLOW_ENV"] = "test"
# Cheap Argon2 parameters keep the suite fast; settings refuse this outside tests.
os.environ["LEXFLOW_PASSWORD_HASH_PROFILE"] = "test-fast"

# What the browser app sends with every change: its origin and the CSRF header.
APP_ORIGIN = "http://localhost:5173"
APP_HEADERS = {"Origin": APP_ORIGIN, "X-LexFlow-Request": "1"}
# A password used only by test accounts in the throwaway test database.
TEST_PASSWORD = "correct horse battery staple"

# Uploads go to a folder of this test session, never to the development store
# (server/var/uploads), even for a test that doesn't choose its own storage.
TEST_UPLOAD_DIR = Path(tempfile.mkdtemp(prefix="lexflow-test-uploads-"))
os.environ["LEXFLOW_UPLOAD_DIR"] = str(TEST_UPLOAD_DIR)
atexit.register(shutil.rmtree, TEST_UPLOAD_DIR, ignore_errors=True)


def database_url(name: str) -> URL:
    """The test server's URL for another database (its name must contain 'test')."""
    return TEST_DATABASE_URL.set(database=name)


def _guard(url: URL) -> str:
    name = url.database
    if not name or "test" not in name:
        raise ValueError(f"refusing to modify database {name!r}")
    return name


def recreate_database(url: URL) -> None:
    """Drop and recreate the database named in ``url`` (connecting to 'postgres')."""
    name = _guard(url)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()


def drop_database(url: URL) -> None:
    name = _guard(url)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


def run_alembic(url: URL, *commands: tuple[str, str]) -> None:
    from alembic import command

    config = alembic_config(url)
    for name, target in commands:
        getattr(command, name)(config, target)


def alembic_config(url: URL) -> Any:
    from alembic.config import Config

    config = Config(str(SERVER_ROOT / "alembic.ini"))
    config.attributes["database_url"] = url.render_as_string(hide_password=False)
    config.attributes["configure_logger"] = False
    return config


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    recreate_database(TEST_DATABASE_URL)
    run_alembic(TEST_DATABASE_URL, ("upgrade", "head"))
    eng = create_engine(TEST_DATABASE_URL)
    yield eng
    eng.dispose()


@pytest.fixture
def connection(engine: Engine) -> Iterator[Connection]:
    with engine.connect() as conn:
        transaction = conn.begin()
        yield conn
        transaction.rollback()


@pytest.fixture
def db(connection: Connection) -> Iterator[Session]:
    """A session whose commits become savepoints inside the test transaction."""
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()


def shared_sessions(db: Session) -> Any:
    """Independent sessions that write into the test transaction.

    Keeps ordinary tests isolated. The real behaviour (committing although the
    request fails) is covered by tests that use ``committed_engine`` and no
    overrides (``tests/test_auth_committed.py``).
    """

    @contextmanager
    def scope() -> Iterator[Session]:
        yield db
        db.commit()  # releases the savepoint; the outer test transaction still rolls back

    return scope


@pytest.fixture
def app(db: Session) -> FastAPI:
    """The real application, with every request using the test transaction."""
    from lexflow.db import get_independent_sessions, get_session
    from lexflow.main import create_app

    application = create_app()
    application.dependency_overrides[get_session] = lambda: db
    application.dependency_overrides[get_independent_sessions] = lambda: shared_sessions(db)
    return application


def http_client(app: FastAPI, **kwargs: Any) -> TestClient:
    """A test client that behaves like the browser app (origin and CSRF header)."""
    return TestClient(app, headers=APP_HEADERS, **kwargs)


@pytest.fixture
def admin(db: Session) -> Any:
    """The Administrator that the ``client`` fixture is signed in as."""
    return make_user(
        db, role="Administrator", email="admin@lexflow.test", name="Test Administrator"
    )


@pytest.fixture
def client(app: FastAPI, admin: Any) -> Iterator[TestClient]:
    """Signed in as an Administrator through the real sign-in endpoint."""
    with http_client(app, raise_server_exceptions=False) as test_client:
        sign_in(test_client, admin)
        yield test_client


@pytest.fixture
def anon_client(app: FastAPI) -> Iterator[TestClient]:
    """Behaves like the browser app, but nobody is signed in."""
    with http_client(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def raw_client(app: FastAPI) -> Iterator[TestClient]:
    """No origin and no CSRF header: for tests of the request checks themselves."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def make_user(
    db: Session,
    *,
    role: str,
    email: str | None = None,
    name: str | None = None,
    password: str | None = TEST_PASSWORD,
    client_id: Any = None,
    **fields: Any,
) -> Any:
    """Add a user (committed into the test transaction) who can sign in with ``password``."""
    from lexflow.auth.passwords import hash_password
    from lexflow.models import User

    tag = uuid.uuid4().hex[:8]
    user = User(
        name=name or f"Test {role} {tag}",
        email=email or f"{role.lower()}-{tag}@lexflow.test",
        role=role,
        client_id=client_id,
        password_hash=hash_password(password, "test-fast") if password else None,
        **fields,
    )
    db.add(user)
    db.commit()
    return user


def sign_in(http: TestClient, user: Any, password: str = TEST_PASSWORD) -> None:
    sign_in_as(http, user.email, password)


def sign_in_as(http: TestClient, email: str, password: str = TEST_PASSWORD) -> None:
    response = http.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text


def committed_user(engine: Engine, *, role: str = "Administrator", email: str | None = None) -> str:
    """A user committed for real (for tests on ``committed_engine``); returns the e-mail."""
    from lexflow.auth.passwords import hash_password
    from lexflow.models import User

    address = email or f"{role.lower()}-{uuid.uuid4().hex[:8]}@lexflow.test"
    with Session(engine) as session, session.begin():
        session.add(
            User(
                name=f"Committed {role}",
                email=address,
                role=role,
                password_hash=hash_password(TEST_PASSWORD, "test-fast"),
            )
        )
    return address


@pytest.fixture
def committed_engine(engine: Engine) -> Iterator[Engine]:
    """For tests that need real commits. All data is removed afterwards."""
    yield engine
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE audit_events, sessions, case_members, documents, timeline_events, "
                "hearings, cases, clients, users, case_number_counters RESTART IDENTITY CASCADE"
            )
        )
