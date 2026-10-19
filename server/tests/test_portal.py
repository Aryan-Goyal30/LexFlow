"""The client portal and its isolation (fixtures: access_fixtures).

Two Client accounts: ``client`` represents the Sattvik case's client (c-005);
``other_client`` represents the client of a different sample case. Sessions
are opened directly, so these tests do not depend on Client sign-in.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from lexflow.auth import sessions
from lexflow.config import get_settings
from lexflow.models import AuditEvent, Case, Document, User
from lexflow.seed import sample_uuid
from tests.access_fixtures import SATTVIK
from tests.conftest import http_client, make_user

PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
SATTVIK_CLIENT = sample_uuid("client", "c-005")
OTHER_CASE = sample_uuid("case", "case-1001")

As = Callable[[str], TestClient]

PUBLIC = {("GET", "/api/health"), ("POST", "/api/auth/login"), ("POST", "/api/auth/logout")}
EVERYONE = {("GET", "/api/auth/me"), ("POST", "/api/auth/password")}


@pytest.fixture
def portal_people(db: Session, people: dict[str, User]) -> dict[str, User]:
    other_case = db.get(Case, OTHER_CASE)
    assert other_case is not None and other_case.client_id != SATTVIK_CLIENT
    return {
        "client": make_user(db, role="Client", name="Sattvik Contact", client_id=SATTVIK_CLIENT),
        "other_client": make_user(
            db, role="Client", name="Other Contact", client_id=other_case.client_id
        ),
    }


@pytest.fixture
def as_client(app: FastAPI, db: Session, portal_people: dict[str, User]) -> Iterator[As]:
    """A browser signed in as a Client account (session opened directly)."""
    settings = get_settings()
    with ExitStack() as stack:

        def get(name: str) -> TestClient:
            token = sessions.start(
                db,
                portal_people[name],
                now=datetime.now(UTC),
                settings=settings,
                user_agent="pytest",
            )
            db.commit()
            http = stack.enter_context(http_client(app, raise_server_exceptions=False))
            http.cookies.set(settings.session_cookie_name, token)
            return http

        yield get


def api_routes(app: FastAPI) -> Iterator[tuple[str, str]]:
    for path, operations in app.openapi()["paths"].items():
        if path.startswith("/api"):
            for method in sorted(operations):
                yield method.upper(), path


def concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)


def upload(http: TestClient, name: str = "Advice.pdf", case_id: Any = SATTVIK) -> dict[str, Any]:
    response = http.post(
        f"/api/cases/{case_id}/documents", files={"file": (name, PDF, "application/pdf")}
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def portal_documents(http: TestClient, case_id: Any = SATTVIK) -> list[dict[str, Any]]:
    response = http.get(f"/api/portal/cases/{case_id}")
    assert response.status_code == 200, response.text
    documents: list[dict[str, Any]] = response.json()["documents"]
    return documents


# --- isolation: the two sides of the API never meet ------------------------------------


def test_a_client_account_reaches_no_staff_route(app: FastAPI, as_client: As) -> None:
    http = as_client("client")
    checked = 0
    for method, path in api_routes(app):
        if (method, path) in PUBLIC | EVERYONE or path.startswith("/api/portal"):
            continue
        response = http.request(method, concrete(path))
        assert response.status_code == 403, (method, path, response.status_code)
        assert response.json()["code"] == "forbidden"
        checked += 1
    assert checked >= 25  # every staff route (28 at the time of writing)


@pytest.mark.parametrize("role", ["admin", "lead", "paralegal"])
def test_staff_accounts_reach_no_portal_route(app: FastAPI, as_: As, role: str) -> None:
    portal = [(m, p) for m, p in api_routes(app) if p.startswith("/api/portal")]
    assert len(portal) == 3
    for method, path in portal:
        response = as_(role).request(method, concrete(path))
        assert response.status_code == 403, (method, path)


def test_a_client_sees_only_their_own_active_cases(as_client: As, db: Session) -> None:
    expected = {
        str(c.id)
        for c in db.scalars(
            select(Case).where(Case.client_id == SATTVIK_CLIENT, Case.archived_at.is_(None))
        )
    }
    listed = {c["id"] for c in as_client("client").get("/api/portal/cases").json()}
    assert listed == expected and str(SATTVIK) in listed
    other = {c["id"] for c in as_client("other_client").get("/api/portal/cases").json()}
    assert str(SATTVIK) not in other and str(OTHER_CASE) in other


def test_another_clients_case_is_not_found(as_client: As) -> None:
    for case_id in (str(OTHER_CASE), str(uuid.uuid4()), "not-an-id"):
        response = as_client("client").get(f"/api/portal/cases/{case_id}")
        assert response.status_code == 404, case_id
        assert response.json()["code"] == "case-not-found"


def test_the_portal_shows_no_internal_details(as_client: As) -> None:
    detail = as_client("client").get(f"/api/portal/cases/{SATTVIK}").json()
    assert set(detail) == {
        "id",
        "caseNumber",
        "title",
        "status",
        "practiceArea",
        "leadAttorney",
        "courtName",
        "openedOn",
        "nextHearing",
        "hearings",
        "documents",
    }
    summary = as_client("client").get("/api/portal/cases").json()[0]
    assert "description" not in summary and "priority" not in summary


def test_an_archived_case_leaves_the_portal(as_: As, as_client: As) -> None:
    as_("admin").post(f"/api/cases/{SATTVIK}/archive")
    assert str(SATTVIK) not in {
        c["id"] for c in as_client("client").get("/api/portal/cases").json()
    }
    assert as_client("client").get(f"/api/portal/cases/{SATTVIK}").status_code == 404


# --- hearings -----------------------------------------------------------------------------


def test_the_client_sees_scheduled_hearings_from_today(as_: As, as_client: As) -> None:
    def schedule(day: str, purpose: str) -> str:
        detail = (
            as_("lead")
            .post(
                f"/api/cases/{SATTVIK}/hearings",
                json={"date": day, "court": "Court Room 4", "purpose": purpose},
            )
            .json()
        )
        return str(next(h["id"] for h in detail["hearings"] if h["purpose"] == purpose))

    schedule("2026-11-02", "Arguments")
    gone = schedule("2026-11-09", "Mention")
    as_("lead").post(f"/api/hearings/{gone}/cancel", json={})
    hearings = as_client("client").get(f"/api/portal/cases/{SATTVIK}").json()["hearings"]
    # The sample hearing of 30 Sep 2026 has passed ("today" is 14 Oct 2026).
    assert hearings == [
        {"date": "2026-11-02", "time": None, "court": "Court Room 4", "purpose": "Arguments"}
    ]


# --- sharing documents -----------------------------------------------------------------------


def test_nothing_is_shared_until_an_advocate_shares_it(
    as_: As, as_client: As, storage_root: Any
) -> None:
    document = upload(as_("lead"))
    assert document["sharedWithClientAt"] is None
    assert portal_documents(as_client("client")) == []
    response = as_client("client").get(f"/api/portal/documents/{document['id']}/download")
    assert response.status_code == 404
    assert response.json()["code"] == "document-not-found"


def test_a_shared_document_reaches_its_client_only(
    as_: As, as_client: As, db: Session, storage_root: Any, portal_people: dict[str, User]
) -> None:
    document = upload(as_("lead"))
    shared = as_("associate").post(f"/api/documents/{document['id']}/share")
    assert shared.status_code == 200
    assert shared.json()["sharedWithClientAt"] is not None

    listed = portal_documents(as_client("client"))
    assert [(d["id"], d["name"]) for d in listed] == [(document["id"], "Advice.pdf")]
    download = as_client("client").get(listed[0]["downloadUrl"])
    assert download.status_code == 200 and download.content == PDF
    assert download.headers["x-content-type-options"] == "nosniff"

    # Another client cannot fetch it, even knowing the id.
    stranger = as_client("other_client").get(listed[0]["downloadUrl"])
    assert stranger.status_code == 404

    events = db.scalars(select(AuditEvent).order_by(AuditEvent.occurred_at)).all()
    assert ("document.shared", people_name(events, "document.shared")) == (
        "document.shared",
        "Associate Advocate",
    )
    reads = [e for e in events if e.action == "document.downloaded"]
    assert [e.actor_id for e in reads] == [portal_people["client"].id]


def people_name(events: Any, action: str) -> str | None:
    return next((e.actor_name for e in events if e.action == action), None)


def test_unsharing_or_deleting_withdraws_it_at_once(
    as_: As, as_client: As, db: Session, storage_root: Any
) -> None:
    first = upload(as_("lead"), "First.pdf")
    second = upload(as_("lead"), "Second.pdf")
    for document in (first, second):
        as_("lead").post(f"/api/documents/{document['id']}/share")
    assert len(portal_documents(as_client("client"))) == 2

    as_("lead").post(f"/api/documents/{first['id']}/unshare")
    as_("lead").delete(f"/api/documents/{second['id']}")
    assert portal_documents(as_client("client")) == []
    for document in (first, second):
        url = f"/api/portal/documents/{document['id']}/download"
        assert as_client("client").get(url).status_code == 404

    # Restoring a deleted document does not share it again.
    as_("lead").post(f"/api/documents/{second['id']}/restore")
    assert portal_documents(as_client("client")) == []
    row = db.get(Document, uuid.UUID(second["id"]))
    assert row is not None
    db.refresh(row)
    assert row.shared_with_client_at is None
    assert "document.unshared" in {e.action for e in db.scalars(select(AuditEvent))}


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("admin", 200),
        ("lead", 200),
        ("associate", 200),
        ("paralegal", 403),
        ("other_advocate", 404),
    ],
)
def test_advocates_on_the_case_share(as_: As, storage_root: Any, role: str, expected: int) -> None:
    document = upload(as_("lead"))
    assert as_(role).post(f"/api/documents/{document['id']}/share").status_code == expected


def test_sample_records_without_a_file_cannot_be_shared(as_: As) -> None:
    sample = sample_uuid("document", "d-18")
    response = as_("lead").post(f"/api/documents/{sample}/share")
    assert response.status_code == 422
    assert response.json()["code"] == "no-file"


def test_nothing_is_shared_on_an_archived_case(as_: As, storage_root: Any) -> None:
    document = upload(as_("lead"))
    as_("admin").post(f"/api/cases/{SATTVIK}/archive")
    response = as_("admin").post(f"/api/documents/{document['id']}/share")
    assert response.status_code == 409
    assert response.json()["code"] == "case-archived"


def test_an_archived_case_withdraws_its_shared_documents(
    as_: As, as_client: As, storage_root: Any
) -> None:
    document = upload(as_("lead"))
    as_("lead").post(f"/api/documents/{document['id']}/share")
    as_("admin").post(f"/api/cases/{SATTVIK}/archive")
    url = f"/api/portal/documents/{document['id']}/download"
    assert as_client("client").get(url).status_code == 404


def test_a_client_account_without_a_client_is_impossible(db: Session) -> None:
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        make_user(db, role="Client", client_id=None)
