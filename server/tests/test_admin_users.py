"""Account administration from the app (fixtures: access_fixtures)."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from lexflow.audit import AuditLog
from lexflow.models import AuditEvent, User
from lexflow.seed import sample_uuid
from lexflow.services import users as service
from tests.conftest import http_client, sign_in_as

As = Callable[[str], TestClient]

TEMPORARY = "a temporary passphrase 42"
NEW_ACCOUNT = {
    "name": "Meera Iyer",
    "email": "meera.iyer@lexflow.test",
    "role": "Advocate",
    "temporaryPassword": TEMPORARY,
}


def admin_routes(app: FastAPI) -> list[tuple[str, str]]:
    return [
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        if path.startswith("/api/admin")
        for method in operations
    ]


def create(http: TestClient, **changes: Any) -> Any:
    return http.post("/api/admin/users", json={**NEW_ACCOUNT, **changes})


def audit_events(db: Session, action: str) -> list[AuditEvent]:
    return list(db.scalars(select(AuditEvent).where(AuditEvent.action == action)))


# --- only administrators ----------------------------------------------------------------


@pytest.mark.parametrize("role", ["lead", "associate", "paralegal", "other_advocate"])
def test_only_administrators_reach_account_administration(app: FastAPI, as_: As, role: str) -> None:
    routes = admin_routes(app)
    assert len(routes) == 8  # accounts (7) and the audit log
    for method, path in routes:
        concrete = re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)
        response = as_(role).request(method, concrete, json={})
        assert response.status_code == 403, (role, method, path)


def test_the_list_shows_accounts_without_secrets(as_: As, people: dict[str, User]) -> None:
    accounts = as_("admin").get("/api/admin/users").json()
    lead = next(a for a in accounts if a["id"] == str(people["lead"].id))
    assert set(lead) == {
        "id",
        "name",
        "email",
        "role",
        "clientId",
        "clientName",
        "isActive",
        "isLocked",
        "canSignIn",
        "mustChangePassword",
        "lastLoginAt",
        "isSample",
    }
    assert lead["canSignIn"] is True and lead["isSample"] is True


# --- creating accounts -------------------------------------------------------------------


def test_a_new_account_must_change_its_temporary_password(
    app: FastAPI, as_: As, db: Session
) -> None:
    response = create(as_("admin"))
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["role"], body["mustChangePassword"], body["canSignIn"]) == (
        "Advocate",
        True,
        True,
    )
    assert TEMPORARY not in response.text
    [event] = audit_events(db, "user.created")
    assert TEMPORARY not in str(event.details)

    with http_client(app) as fresh:
        sign_in_as(fresh, NEW_ACCOUNT["email"], TEMPORARY)
        assert fresh.get("/api/cases").json()["code"] == "password-change-required"


def test_a_client_account_represents_a_client(as_: As) -> None:
    client_id = str(sample_uuid("client", "c-005"))
    response = create(
        as_("admin"), role="Client", email="contact@client.example", clientId=client_id
    )
    assert response.status_code == 201, response.text
    assert response.json()["clientId"] == client_id
    assert response.json()["clientName"]


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"role": "Client"}, "clientId"),
        ({"role": "Client", "clientId": str(uuid.uuid4())}, "clientId"),
        ({"clientId": str(sample_uuid("client", "c-005"))}, "clientId"),
        ({"email": "aryan.goyal@lexflow.test"}, "email"),
        ({"email": "not-an-address"}, "email"),
        ({"name": "M"}, "name"),
        ({"temporaryPassword": "short"}, "temporaryPassword"),
        ({"temporaryPassword": "meera.iyer@lexflow.test"}, "temporaryPassword"),
    ],
)
def test_new_accounts_are_checked(as_: As, changes: dict[str, str], field: str) -> None:
    response = create(as_("admin"), **changes)
    assert response.status_code == 422, response.text
    assert [e["field"] for e in response.json()["errors"]] == [field]


# --- editing, disabling, unlocking, resetting -----------------------------------------------


def test_name_and_email_can_change_but_not_to_a_taken_address(as_: As, db: Session) -> None:
    account = create(as_("admin")).json()
    changed = as_("admin").patch(
        f"/api/admin/users/{account['id']}", json={"name": "Meera R. Iyer"}
    )
    assert changed.status_code == 200 and changed.json()["name"] == "Meera R. Iyer"
    taken = as_("admin").patch(
        f"/api/admin/users/{account['id']}", json={"email": "aryan.goyal@lexflow.test"}
    )
    assert taken.status_code == 422
    role = as_("admin").patch(f"/api/admin/users/{account['id']}", json={"role": "Administrator"})
    assert role.status_code == 422  # the role cannot change
    assert [e.details for e in audit_events(db, "user.updated")] == [{"fields": ["name"]}]


def test_disabling_ends_the_sessions_and_enabling_restores_sign_in(
    as_: As, people: dict[str, User]
) -> None:
    lead_browser = as_("lead")
    assert lead_browser.get("/api/cases").status_code == 200
    disabled = as_("admin").post(f"/api/admin/users/{people['lead'].id}/disable")
    assert disabled.status_code == 200 and disabled.json()["isActive"] is False
    assert lead_browser.get("/api/cases").status_code == 401

    enabled = as_("admin").post(f"/api/admin/users/{people['lead'].id}/enable")
    assert enabled.json()["isActive"] is True


def test_an_administrator_cannot_disable_or_reset_their_own_account(
    as_: As, people: dict[str, User]
) -> None:
    me = people["admin"].id
    for response in (
        as_("admin").post(f"/api/admin/users/{me}/disable"),
        as_("admin").post(f"/api/admin/users/{me}/password", json={"temporaryPassword": TEMPORARY}),
    ):
        assert response.status_code == 409
    assert as_("admin").get("/api/cases").status_code == 200  # still signed in


def test_the_last_active_administrator_cannot_be_disabled(
    db: Session, people: dict[str, User]
) -> None:
    # Only reachable if another account could act; the rule holds regardless.
    with pytest.raises(Exception, match="last active administrator"):
        service.set_active(
            db,
            people["admin"].id,
            active=False,
            actor=people["lead"],
            audit=AuditLog(None),  # type: ignore[arg-type]
            now=datetime.now(UTC),
        )


def test_unlocking_clears_a_lockout(as_: As, db: Session, people: dict[str, User]) -> None:
    lead = people["lead"]
    lead.failed_login_count, lead.locked_until = 5, datetime.now(UTC) + timedelta(minutes=10)
    db.commit()
    assert as_("admin").get("/api/admin/users").json()  # list works while locked
    response = as_("admin").post(f"/api/admin/users/{lead.id}/unlock")
    assert response.status_code == 200 and response.json()["isLocked"] is False
    db.refresh(lead)
    unlocked = db.get(User, lead.id)
    assert unlocked is not None
    assert unlocked.failed_login_count == 0 and unlocked.locked_until is None
    assert len(audit_events(db, "user.unlocked")) == 1


def test_a_reset_gives_a_temporary_password_and_ends_sessions(
    app: FastAPI, as_: As, db: Session, people: dict[str, User]
) -> None:
    lead_browser = as_("lead")
    response = as_("admin").post(
        f"/api/admin/users/{people['lead'].id}/password", json={"temporaryPassword": TEMPORARY}
    )
    assert response.status_code == 200 and response.json()["mustChangePassword"] is True
    assert TEMPORARY not in response.text
    assert lead_browser.get("/api/cases").status_code == 401
    with http_client(app) as fresh:
        sign_in_as(fresh, "aryan.goyal@lexflow.test", TEMPORARY)
        assert fresh.get("/api/auth/me").json()["mustChangePassword"] is True
    [event] = audit_events(db, "user.password_set")
    assert event.details == {"temporary": "true"}


def test_unknown_accounts_are_not_found(as_: As) -> None:
    for user_id in (str(uuid.uuid4()), "nope"):
        response = as_("admin").post(f"/api/admin/users/{user_id}/unlock")
        assert response.status_code == 404
        assert response.json()["code"] == "user-not-found"
