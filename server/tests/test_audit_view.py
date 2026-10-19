"""Reading the audit log (Administrators only; fixtures: access_fixtures)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lexflow.models import AuditEvent, User
from tests.access_fixtures import SATTVIK
from tests.conftest import TEST_PASSWORD

As = Callable[[str], TestClient]


def page(http: TestClient, **params: Any) -> Any:
    response = http.get("/api/admin/audit", params=params)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def activity(as_: As) -> None:
    """Some events: an edit, a refused look at a case, an archive and a restore."""
    as_("lead").patch(f"/api/cases/{SATTVIK}", json={"priority": "Critical"})
    as_("other_advocate").get(f"/api/cases/{SATTVIK}")  # denied, audited
    as_("admin").post(f"/api/cases/{SATTVIK}/archive")
    as_("admin").post(f"/api/cases/{SATTVIK}/unarchive")


@pytest.mark.parametrize("role", ["lead", "associate", "paralegal", "other_advocate"])
def test_only_administrators_read_it(as_: As, role: str) -> None:
    assert as_(role).get("/api/admin/audit").status_code == 403


def test_it_is_read_only(as_: As) -> None:
    for method in ("POST", "PATCH", "PUT", "DELETE"):
        assert as_("admin").request(method, "/api/admin/audit").status_code == 405, method


def test_events_come_newest_first_with_their_case(
    as_: As, db: Session, activity: None, people: dict[str, User]
) -> None:
    events = page(as_("admin"), limit=200)["events"]
    total = db.scalar(select(func.count()).select_from(AuditEvent))
    assert len(events) == total
    stamps = [e["occurredAt"] for e in events]
    assert stamps == sorted(stamps, reverse=True)
    updated = next(e for e in events if e["action"] == "case.updated")
    assert updated["actorName"] == "Aryan Goyal" and updated["caseNumber"]
    assert updated["details"] == {"fields": ["priority"], "newPriority": "Critical"}


def test_no_secret_reaches_the_viewer(as_: As, activity: None) -> None:
    body = as_("admin").get("/api/admin/audit", params={"limit": 200}).text
    assert TEST_PASSWORD not in body
    assert "lexflow_session" not in body


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"action": "case.updated"}, {"case.updated"}),
        ({"action": "case."}, {"case.updated", "case.archived", "case.restored"}),
        ({"outcome": "denied"}, None),
    ],
)
def test_filters(
    as_: As, activity: None, params: dict[str, str], expected: set[str] | None
) -> None:
    events = page(as_("admin"), limit=200, **params)["events"]
    assert events
    if expected is not None:
        assert {e["action"] for e in events} == expected
    else:
        assert {e["outcome"] for e in events} == {"denied"}
        assert {e["actorName"] for e in events} == {"Rajat Deshpande"}


def test_filter_by_case_and_person(as_: As, activity: None, people: dict[str, User]) -> None:
    by_case = page(as_("admin"), caseId=str(SATTVIK), limit=200)["events"]
    assert by_case and {e["caseId"] for e in by_case} == {str(SATTVIK)}
    by_admin = page(as_("admin"), actorId=str(people["admin"].id), limit=200)["events"]
    assert {e["action"] for e in by_admin} >= {"case.archived", "case.restored"}
    assert {e["actorId"] for e in by_admin} == {str(people["admin"].id)}


def test_date_ranges(as_: As, activity: None) -> None:
    assert page(as_("admin"), **{"from": "2099-01-01"})["events"] == []
    assert page(as_("admin"), **{"to": "2000-01-01"})["events"] == []
    response = as_("admin").get(
        "/api/admin/audit", params={"from": "2026-10-14", "to": "2026-10-13"}
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "to"


def test_pages_cover_everything_once(as_: As, activity: None) -> None:
    everything = [e["id"] for e in page(as_("admin"), limit=200)["events"]]
    seen: list[str] = []
    before: str | None = None
    while True:
        params: dict[str, Any] = {"limit": 2}
        if before:
            params["before"] = before
        body = page(as_("admin"), **params)
        seen += [e["id"] for e in body["events"]]
        before = body["nextBefore"]
        if before is None:
            break
    assert seen == everything


def test_an_unknown_cursor_is_refused(as_: As) -> None:
    response = as_("admin").get("/api/admin/audit", params={"before": str(uuid.uuid4())})
    assert response.status_code == 422
