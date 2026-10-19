"""Scheduling, changing and cancelling hearings (fixtures: access_fixtures).

"Today" is fixed at 2026-10-14; the Sattvik case's only sample hearing
(30 Sep 2026) has passed.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from lexflow.models import AuditEvent, Hearing, User
from lexflow.seed import sample_uuid
from tests.access_fixtures import SATTVIK

As = Callable[[str], TestClient]

FIRST_LISTING = {
    "date": "2026-11-02",
    "time": "10:30",
    "court": "High Court of Bombay, Court Room 12",
    "purpose": "Arguments on interim relief",
}
SAMPLE_HEARING = sample_uuid("hearing", "h-5")


def schedule(http: TestClient, **changes: Any) -> Any:
    return http.post(f"/api/cases/{SATTVIK}/hearings", json={**FIRST_LISTING, **changes})


def new_hearing(detail: dict[str, Any]) -> dict[str, Any]:
    found: dict[str, Any] = next(h for h in detail["hearings"] if h["date"] == "2026-11-02")
    return found


def actions(db: Session) -> list[str]:
    return list(db.scalars(select(AuditEvent.action).order_by(AuditEvent.occurred_at)))


# --- who may manage hearings ----------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("admin", 201),
        ("lead", 201),
        ("associate", 201),
        ("paralegal", 201),
        ("other_advocate", 404),
        ("other_paralegal", 404),
    ],
)
def test_everyone_on_the_case_staff_schedules_hearings(as_: As, role: str, expected: int) -> None:
    assert schedule(as_(role)).status_code == expected


@pytest.mark.parametrize("role", ["other_advocate", "other_paralegal"])
def test_a_hearing_on_a_case_you_cannot_see_is_not_found(as_: As, db: Session, role: str) -> None:
    for response in (
        as_(role).patch(f"/api/hearings/{SAMPLE_HEARING}", json={"court": "Elsewhere"}),
        as_(role).post(f"/api/hearings/{SAMPLE_HEARING}/cancel", json={}),
    ):
        assert response.status_code == 404
        assert response.json()["code"] == "hearing-not-found"
    hearing = db.get(Hearing, SAMPLE_HEARING)
    assert hearing is not None and hearing.court != "Elsewhere" and hearing.status == "Scheduled"
    denied = db.scalars(select(AuditEvent).where(AuditEvent.outcome == "denied")).all()
    assert {e.target_type for e in denied} == {"hearing"}


def test_unknown_or_malformed_ids_are_not_found(as_: As) -> None:
    for hearing_id in (str(uuid.uuid4()), "not-an-id"):
        response = as_("admin").patch(f"/api/hearings/{hearing_id}", json={"court": "X Court"})
        assert response.status_code == 404
        assert response.json()["code"] == "hearing-not-found"


# --- scheduling ---------------------------------------------------------------------------


def test_scheduling_adds_the_hearing_and_makes_it_the_next_one(
    as_: As, db: Session, people: dict[str, User]
) -> None:
    response = schedule(as_("paralegal"))
    assert response.status_code == 201, response.text
    detail = response.json()
    hearing = new_hearing(detail)
    assert hearing | {"id": None} == {
        **FIRST_LISTING,
        "id": None,
        "status": "Scheduled",
        "cancellationReason": None,
        "isSample": False,
    }
    assert detail["nextHearing"] == "2026-11-02"
    last = detail["timeline"][-1]
    assert last["label"] == "Hearing scheduled"
    assert last["description"] == (
        "Arguments on interim relief on 2 Nov 2026 at 10:30, High Court of Bombay, Court Room 12."
    )
    assert last["actor"]["name"] == "Assigned Paralegal"
    row = db.get(Hearing, uuid.UUID(hearing["id"]))
    assert row is not None and row.created_by_id == people["paralegal"].id
    assert "hearing.scheduled" in actions(db)

    upcoming = as_("lead").get("/api/hearings/upcoming?limit=50").json()
    assert hearing["id"] in {h["id"] for h in upcoming}


def test_the_time_may_be_left_for_the_court_to_list(as_: As) -> None:
    detail = schedule(as_("lead"), time=" ").json()
    assert new_hearing(detail)["time"] is None
    assert detail["timeline"][-1]["description"].startswith(
        "Arguments on interim relief on 2 Nov 2026, "
    )


@pytest.mark.parametrize(
    ("changes", "field", "message"),
    [
        ({"date": "2026-10-13"}, "date", "The hearing date cannot be in the past."),
        ({"time": "25:00"}, "time", "Enter the time as HH:MM (24-hour), or leave it blank."),
        ({"time": "9:30"}, "time", "Enter the time as HH:MM (24-hour), or leave it blank."),
        ({"court": "   "}, "court", "Enter the court or forum."),
        ({"purpose": ""}, "purpose", "Enter the purpose of the hearing."),
        ({"purpose": "x" * 201}, "purpose", "Keep this under 201 characters."),
    ],
)
def test_scheduling_checks_each_field(
    as_: As, db: Session, changes: dict[str, str], field: str, message: str
) -> None:
    response = schedule(as_("lead"), **changes)
    assert response.status_code == 422
    assert response.json()["errors"] == [{"field": field, "message": message}]
    assert db.scalars(select(Hearing).where(Hearing.case_id == SATTVIK)).all() == [
        db.get(Hearing, SAMPLE_HEARING)
    ]


def test_today_is_not_in_the_past(as_: As) -> None:
    assert schedule(as_("lead"), date="2026-10-14").status_code == 201


def test_unknown_fields_are_refused(as_: As) -> None:
    response = schedule(as_("lead"), status="Cancelled")
    assert response.status_code == 422


# --- changing -------------------------------------------------------------------------------


def test_changing_a_hearing_records_what_changed(as_: As, db: Session) -> None:
    hearing = new_hearing(schedule(as_("lead")).json())
    response = as_("associate").patch(
        f"/api/hearings/{hearing['id']}",
        json={"date": "2026-11-05", "time": None, "court": "Court Room 14"},
    )
    assert response.status_code == 200, response.text
    detail = response.json()
    changed = next(h for h in detail["hearings"] if h["id"] == hearing["id"])
    assert (changed["date"], changed["time"], changed["court"]) == (
        "2026-11-05",
        None,
        "Court Room 14",
    )
    assert detail["timeline"][-1]["label"] == "Hearing updated"
    assert detail["timeline"][-1]["description"] == (
        "Arguments on interim relief (5 Nov 2026): Date moved from 2 Nov 2026 to 5 Nov 2026. "
        "Time cleared (to be notified). Court updated."
    )
    assert actions(db).count("hearing.updated") == 1


def test_an_unchanged_hearing_records_nothing(as_: As, db: Session) -> None:
    hearing = new_hearing(schedule(as_("lead")).json())
    before = len(as_("lead").get(f"/api/cases/{SATTVIK}").json()["timeline"])
    response = as_("lead").patch(
        f"/api/hearings/{hearing['id']}", json={"court": FIRST_LISTING["court"]}
    )
    assert response.status_code == 200
    assert len(response.json()["timeline"]) == before
    assert "hearing.updated" not in actions(db)


def test_a_hearing_cannot_be_moved_into_the_past(as_: As) -> None:
    hearing = new_hearing(schedule(as_("lead")).json())
    response = as_("lead").patch(f"/api/hearings/{hearing['id']}", json={"date": "2026-01-01"})
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "date"


def test_required_hearing_fields_cannot_be_emptied(as_: As) -> None:
    for field in ("date", "court", "purpose"):
        response = as_("lead").patch(f"/api/hearings/{SAMPLE_HEARING}", json={field: None})
        assert response.status_code == 422, field


# --- cancelling -----------------------------------------------------------------------------


def test_a_cancelled_hearing_is_kept_but_no_longer_next_or_upcoming(as_: As, db: Session) -> None:
    hearing = new_hearing(schedule(as_("lead")).json())
    response = as_("paralegal").post(
        f"/api/hearings/{hearing['id']}/cancel", json={"reason": "Bench not sitting."}
    )
    assert response.status_code == 200, response.text
    detail = response.json()
    cancelled = next(h for h in detail["hearings"] if h["id"] == hearing["id"])
    assert cancelled["status"] == "Cancelled"
    assert cancelled["cancellationReason"] == "Bench not sitting."
    assert detail["nextHearing"] == "2026-09-30"  # back to the latest past hearing
    assert detail["timeline"][-1]["description"] == (
        "Arguments on interim relief on 2 Nov 2026 at 10:30 was cancelled. "
        "Reason: Bench not sitting."
    )
    upcoming = as_("lead").get("/api/hearings/upcoming?limit=50").json()
    assert hearing["id"] not in {h["id"] for h in upcoming}
    listed = {c["id"]: c for c in as_("lead").get("/api/cases").json()}
    assert listed[str(SATTVIK)]["nextHearing"] == "2026-09-30"

    # Cancelling again changes nothing; a cancelled hearing cannot be edited.
    again = as_("lead").post(f"/api/hearings/{hearing['id']}/cancel", json={})
    assert [e["label"] for e in again.json()["timeline"]].count("Hearing cancelled") == 1
    edit = as_("lead").patch(f"/api/hearings/{hearing['id']}", json={"court": "Elsewhere"})
    assert edit.status_code == 409
    assert edit.json()["code"] == "hearing-cancelled"
    assert actions(db).count("hearing.cancelled") == 1


def test_a_reason_is_optional_but_limited(as_: As) -> None:
    long = as_("lead").post(f"/api/hearings/{SAMPLE_HEARING}/cancel", json={"reason": "x" * 501})
    assert long.status_code == 422
    assert long.json()["errors"][0]["field"] == "reason"
    plain = as_("lead").post(f"/api/hearings/{SAMPLE_HEARING}/cancel", json={"reason": "  "})
    assert plain.status_code == 200
    sample = next(h for h in plain.json()["hearings"] if h["id"] == str(SAMPLE_HEARING))
    assert sample["cancellationReason"] is None
    assert plain.json()["timeline"][-1]["description"].endswith("was cancelled.")


# --- archived cases -----------------------------------------------------------------------


def test_nothing_changes_on_an_archived_case(as_: As) -> None:
    assert as_("admin").post(f"/api/cases/{SATTVIK}/archive").status_code == 200
    for response in (
        schedule(as_("admin")),
        as_("admin").patch(f"/api/hearings/{SAMPLE_HEARING}", json={"court": "Elsewhere"}),
        as_("admin").post(f"/api/hearings/{SAMPLE_HEARING}/cancel", json={}),
    ):
        assert response.status_code == 409
        assert response.json()["code"] == "case-archived"
