"""Client records: seeing, adding and changing them (fixtures: access_fixtures).

The Sattvik case (case-1005) is for the sample client c-005; Aryan Goyal leads it.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from lexflow.models import AuditEvent, Client
from lexflow.seed import sample_uuid
from tests.access_fixtures import SATTVIK

As = Callable[[str], TestClient]

SATTVIK_CLIENT = sample_uuid("client", "c-005")
NEW_CLIENT = {
    "name": "Example Traders LLP",
    "email": "accounts@traders.example",
    "phone": "+91 00000 11111",
    "company": "Example Traders LLP",
}


def actions(db: Session) -> list[str]:
    return list(db.scalars(select(AuditEvent.action).order_by(AuditEvent.occurred_at)))


# --- seeing clients ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "status", "can_edit"),
    [
        ("admin", 200, True),
        ("lead", 200, True),
        ("associate", 200, True),
        ("paralegal", 200, False),
        ("other_advocate", 404, None),
        ("other_paralegal", 404, None),
    ],
)
def test_a_client_is_visible_through_their_cases(
    as_: As, role: str, status: int, can_edit: bool | None
) -> None:
    response = as_(role).get(f"/api/clients/{SATTVIK_CLIENT}")
    assert response.status_code == status
    if status == 200:
        body = response.json()
        assert body["canEdit"] is can_edit
        assert [c["id"] for c in body["cases"]] == [str(SATTVIK)]
    else:
        assert response.json()["code"] == "client-not-found"


def test_an_administrator_sees_all_cases_of_a_client(as_: As, db: Session) -> None:
    body = as_("admin").get(f"/api/clients/{SATTVIK_CLIENT}").json()
    client = db.get(Client, SATTVIK_CLIENT)
    assert client is not None and body["name"] == client.name
    assert {"email", "phone", "company"} <= set(body)


def test_archived_cases_are_listed_on_the_client(as_: As) -> None:
    as_("admin").post(f"/api/cases/{SATTVIK}/archive")
    cases = as_("lead").get(f"/api/clients/{SATTVIK_CLIENT}").json()["cases"]
    assert [c["archivedAt"] is not None for c in cases] == [True]


def test_unknown_or_malformed_ids_are_not_found(as_: As) -> None:
    for client_id in (str(uuid.uuid4()), "nope"):
        assert as_("admin").get(f"/api/clients/{client_id}").status_code == 404


# --- adding clients ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "expected"),
    [("admin", 201), ("lead", 201), ("paralegal", 403), ("other_paralegal", 403)],
)
def test_administrators_and_advocates_add_clients(as_: As, role: str, expected: int) -> None:
    assert as_(role).post("/api/clients", json=NEW_CLIENT).status_code == expected


def test_a_new_client_is_saved_and_audited(as_: As, db: Session) -> None:
    response = as_("lead").post("/api/clients", json={**NEW_CLIENT, "company": "  "})
    assert response.status_code == 201
    body = response.json()
    assert response.headers["location"] == f"/api/clients/{body['id']}"
    assert body | {"id": None} == {
        **NEW_CLIENT,
        "company": None,
        "id": None,
        "isSample": False,
    }
    assert "client.created" in actions(db)
    # Offered for new cases straight away.
    options = as_("lead").get("/api/clients/options").json()
    assert body["id"] in {o["id"] for o in options}


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("name", "A", "Enter the client's name (at least 2 characters)."),
        ("email", "not-an-address", "Enter an e-mail address such as name@example.com."),
        ("phone", "call me", "Enter a phone number: digits, spaces, +, - or brackets (7 to 20)."),
        ("company", "x" * 201, "Keep this under 201 characters."),
    ],
)
def test_client_details_are_checked(as_: As, field: str, value: str, message: str) -> None:
    response = as_("admin").post("/api/clients", json={**NEW_CLIENT, field: value})
    assert response.status_code == 422
    assert response.json()["errors"] == [{"field": field, "message": message}]


# --- changing clients ---------------------------------------------------------------------


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
def test_who_may_change_a_client(as_: As, role: str, expected: int) -> None:
    response = as_(role).patch(f"/api/clients/{SATTVIK_CLIENT}", json={"phone": "+91 00000 22222"})
    assert response.status_code == expected


def test_changes_are_saved_and_audited_by_field_name(as_: As, db: Session) -> None:
    response = as_("lead").patch(
        f"/api/clients/{SATTVIK_CLIENT}",
        json={"email": "legal@sattvik.example", "company": None},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "legal@sattvik.example"
    assert response.json()["company"] is None
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "client.updated")).one()
    assert event.details == {"fields": ["email", "company"]}  # names, not values


def test_an_unchanged_client_records_nothing(as_: As, db: Session) -> None:
    client = db.get(Client, SATTVIK_CLIENT)
    assert client is not None
    as_("lead").patch(f"/api/clients/{SATTVIK_CLIENT}", json={"name": client.name})
    assert "client.updated" not in actions(db)


def test_a_refused_change_is_audited_and_changes_nothing(as_: As, db: Session) -> None:
    before = db.get(Client, SATTVIK_CLIENT)
    assert before is not None
    phone = before.phone
    as_("paralegal").patch(f"/api/clients/{SATTVIK_CLIENT}", json={"phone": "+91 00000 99999"})
    db.expire_all()
    after = db.get(Client, SATTVIK_CLIENT)
    assert after is not None and after.phone == phone
    denied = db.scalars(select(AuditEvent).where(AuditEvent.outcome == "denied")).all()
    assert [(e.action, e.target_type) for e in denied] == [("client.update", "client")]


def test_required_details_cannot_be_emptied(as_: As) -> None:
    for field in ("name", "email", "phone"):
        response = as_("admin").patch(f"/api/clients/{SATTVIK_CLIENT}", json={field: None})
        assert response.status_code == 422, field


def test_clients_cannot_be_deleted(as_: As) -> None:
    response = as_("admin").delete(f"/api/clients/{SATTVIK_CLIENT}")
    assert response.status_code == 405
