"""Request checks (Host, CSRF header, Origin) and safe error handling."""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from lexflow.clock import get_today
from lexflow.models import TimelineEvent
from lexflow.security import has_cookie, host_name, normalise_origin
from lexflow.seed import sample_uuid
from lexflow.seed.loader import load_sample_data
from tests.conftest import (
    APP_HEADERS,
    committed_user,
    http_client,
    make_user,
    sign_in,
    sign_in_as,
)
from tests.test_cases import TODAY, new_case

SATTVIK = str(sample_uuid("case", "case-1005"))


@pytest.fixture
def seeded(db: Session, app: FastAPI) -> Session:
    load_sample_data(db)
    db.commit()
    app.dependency_overrides[get_today] = lambda: TODAY
    return db


# --- DNS rebinding: only loopback Host names are answered -----------------------


@pytest.mark.parametrize("host", ["evil.example", "evil.example:8000", "192.168.1.20:8000"])
def test_foreign_host_header_is_refused(client: TestClient, host: str) -> None:
    response = client.get("/api/cases", headers={"host": host})

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "invalid-host"
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize("host", ["localhost:8000", "127.0.0.1:8000", "[::1]:8000", "LOCALHOST"])
def test_loopback_host_headers_are_accepted(client: TestClient, host: str) -> None:
    assert client.get("/api/health", headers={"host": host}).status_code == 200


def test_host_name_parsing() -> None:
    assert host_name("localhost:5173") == "localhost"
    assert host_name("[::1]:8000") == "::1"
    assert host_name("127.0.0.1") == "127.0.0.1"
    assert host_name("") == ""


# --- cross-site request forgery: header, exact origin, origin with a cookie ------


def _change_attempts(http: TestClient, headers: dict[str, str]) -> list[Any]:
    return [
        http.post("/api/cases", json=new_case(), headers=headers),
        http.patch(f"/api/cases/{SATTVIK}", json={"status": "Closed"}, headers=headers),
        http.post(
            f"/api/cases/{SATTVIK}/documents",
            files={"file": ("A.pdf", b"%PDF-1.4\n", "application/pdf")},
            headers=headers,
        ),
        http.delete(f"/api/documents/{sample_uuid('document', 'd-18')}", headers=headers),
        http.post(
            "/api/auth/login", json={"email": "x@lexflow.test", "password": "x"}, headers=headers
        ),
    ]


def test_changes_without_the_app_header_are_refused(
    raw_client: TestClient, client: TestClient, seeded: Session
) -> None:
    # Even from the right origin: a cross-site form can't add the header.
    for response in _change_attempts(raw_client, {"origin": "http://localhost:5173"}):
        assert response.status_code == 403, response.text
        assert response.json()["code"] == "csrf-header-missing"
    assert client.get(f"/api/cases/{SATTVIK}").json()["status"] == "In Progress"


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example",
        "http://192.168.1.20:5173",
        "null",
        "http://localhost:3000",  # another program on this computer
        "http://127.0.0.1:8000",  # e.g. Swagger UI: read-only by design
        "https://localhost:5173",  # right host and port, wrong scheme
        "http://localhost.evil.example:5173",
    ],
)
def test_changes_from_other_origins_are_refused(
    raw_client: TestClient, client: TestClient, seeded: Session, origin: str
) -> None:
    for response in _change_attempts(raw_client, {"origin": origin, "x-lexflow-request": "1"}):
        assert response.status_code == 403, response.text
        assert response.json()["code"] == "forbidden-origin"
    assert client.get(f"/api/cases/{SATTVIK}").json()["status"] == "In Progress"


@pytest.mark.parametrize(
    "origin", ["http://localhost:5173", "http://127.0.0.1:5173", "HTTP://LOCALHOST:5173/"]
)
def test_changes_from_the_local_front_end_are_accepted(
    client: TestClient, seeded: Session, origin: str
) -> None:
    response = client.patch(
        f"/api/cases/{SATTVIK}",
        json={"priority": "Critical"},
        headers={"origin": origin, "x-lexflow-request": "1"},
    )
    assert response.status_code == 200, response.text


def test_the_header_alone_does_not_make_a_change_acceptable(
    raw_client: TestClient, seeded: Session
) -> None:
    # Past the CSRF checks, a request without a session is still refused.
    response = raw_client.patch(
        f"/api/cases/{SATTVIK}", json={"priority": "Critical"}, headers={"x-lexflow-request": "1"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "not-authenticated"


def test_a_request_with_the_session_cookie_must_name_its_origin(
    app: FastAPI, seeded: Session
) -> None:
    user = make_user(seeded, role="Administrator")
    with http_client(app, raise_server_exceptions=False) as http:
        sign_in(http, user)
        cookies = dict(http.cookies)
    # Browsers always send Origin with a change; a cookie without one is refused.
    with TestClient(app, raise_server_exceptions=False, cookies=cookies) as bare:
        response = bare.patch(
            f"/api/cases/{SATTVIK}",
            json={"priority": "Critical"},
            headers={"x-lexflow-request": "1"},
        )
    assert response.status_code == 403
    assert response.json()["code"] == "origin-required"


def test_reads_are_not_blocked_by_origin(client: TestClient, seeded: Session) -> None:
    # A cross-site page can't read the response anyway (no CORS headers).
    response = client.get("/api/cases", headers={"origin": "https://evil.example"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_origin_and_cookie_helpers() -> None:
    assert normalise_origin(" HTTP://LocalHost:5173/ ") == "http://localhost:5173"
    assert has_cookie("a=1; lexflow_session=abc", "lexflow_session")
    assert not has_cookie("a=1", "lexflow_session")
    assert not has_cookie(None, "lexflow_session")
    assert APP_HEADERS["X-LexFlow-Request"] == "1"


# --- unexpected errors: problem response, nothing sensitive logged --------------


def test_unexpected_error_is_problem_and_logs_no_message(
    app: FastAPI, admin: Any, caplog: pytest.LogCaptureFixture
) -> None:
    marker = "CONFIDENTIAL-CLIENT-DATA-4711"

    @app.get("/api/boom")
    def boom() -> None:
        raise RuntimeError(f"failed while handling {marker}")

    with caplog.at_level(logging.INFO), http_client(app, raise_server_exceptions=True) as client:
        sign_in(client, admin)
        # raise_server_exceptions=True: the error must not escape the app at all.
        response = client.get("/api/boom")

    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "internal-error"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert marker not in response.text
    assert "RuntimeError" in caplog.text
    assert marker not in caplog.text
    access = [r for r in caplog.records if r.name == "lexflow.access"]
    assert any("GET /api/boom 500" in r.getMessage() for r in access)


def test_database_errors_would_not_include_values(engine: Engine) -> None:
    from lexflow.db import engine_for
    from tests.conftest import TEST_DATABASE_URL

    app_engine = engine_for(TEST_DATABASE_URL.render_as_string(hide_password=False))
    assert app_engine.hide_parameters is True


# --- input that PostgreSQL can't store ------------------------------------------


def test_nul_characters_are_a_field_error(client: TestClient, seeded: Session) -> None:
    created = client.post("/api/cases", json=new_case(title="Test\u0000 matter"))
    assert created.status_code == 422
    assert [e["field"] for e in created.json()["errors"]] == ["title"]

    patched = client.patch(f"/api/cases/{SATTVIK}", json={"courtName": "Court\u0000 7"})
    assert patched.status_code == 422
    assert [e["field"] for e in patched.json()["errors"]] == ["courtName"]


def test_malformed_json_names_the_request_not_an_offset(
    client: TestClient, seeded: Session
) -> None:
    response = client.post(
        "/api/cases", content=b"{not json", headers={"content-type": "application/json"}
    )
    assert response.status_code == 422
    assert [e["field"] for e in response.json()["errors"]] == ["request"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "   "),  # whitespace only
        ("title", "x" * 301),
        ("description", "         "),
        ("description", "x" * 10_001),
        ("courtName", "x" * 301),
        ("opposingParty", "x" * 301),
    ],
)
def test_length_and_blank_limits(
    client: TestClient, seeded: Session, field: str, value: str
) -> None:
    response = client.post("/api/cases", json=new_case(**{field: value}))
    assert response.status_code == 422
    assert [e["field"] for e in response.json()["errors"]] == [field]


# --- concurrent updates record history once -------------------------------------


@pytest.fixture
def committed_sample(committed_engine: Engine) -> Iterator[None]:
    with Session(committed_engine) as session, session.begin():
        load_sample_data(session)
    yield


def test_double_submitted_update_records_one_entry(
    committed_engine: Engine, committed_sample: None
) -> None:
    from lexflow.main import create_app

    email = committed_user(committed_engine)
    app = create_app()  # real sessions: each request commits
    app.dependency_overrides[get_today] = lambda: TODAY
    workers = 6
    barrier = threading.Barrier(workers)
    statuses: list[int] = []

    def submit() -> None:
        with http_client(app) as http:
            sign_in_as(http, email)
            barrier.wait()
            statuses.append(
                http.patch(f"/api/cases/{SATTVIK}", json={"status": "Closed"}).status_code
            )

    threads = [threading.Thread(target=submit) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert statuses == [200] * workers
    with Session(committed_engine) as session:
        entries = session.scalar(
            select(func.count())
            .select_from(TimelineEvent)
            .where(
                TimelineEvent.case_id == uuid.UUID(SATTVIK),
                TimelineEvent.label == "Case details updated",
            )
        )
    assert entries == 1
