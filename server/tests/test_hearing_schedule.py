"""The firm-wide hearing schedule, ``GET /api/hearings`` (fixtures: access_fixtures).

"Today" is fixed at 2026-10-14.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from lexflow.models import Case, Hearing
from tests.access_fixtures import SATTVIK

As = Callable[[str], TestClient]


def schedule(http: TestClient, **params: Any) -> Any:
    response = http.get("/api/hearings", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def add(http: TestClient, day: str, purpose: str, time: str | None = None) -> str:
    detail = http.post(
        f"/api/cases/{SATTVIK}/hearings",
        json={"date": day, "time": time, "court": "Court Room 7", "purpose": purpose},
    ).json()
    return str(next(h["id"] for h in detail["hearings"] if h["purpose"] == purpose))


def expected_ids(db: Session, start: str, end: str, case_ids: set[Any] | None = None) -> list[str]:
    query = (
        select(Hearing.id)
        .join(Case, Case.id == Hearing.case_id)
        .where(
            Hearing.hearing_date >= date.fromisoformat(start),
            Hearing.hearing_date <= date.fromisoformat(end),
            Hearing.status == "Scheduled",
            Case.archived_at.is_(None),
        )
    )
    if case_ids is not None:
        query = query.where(Hearing.case_id.in_(case_ids))
    return sorted(str(i) for i in db.scalars(query))


def test_an_administrator_sees_every_case_from_today_for_30_days(as_: As, db: Session) -> None:
    add(as_("lead"), "2026-10-20", "Mention")
    body = schedule(as_("admin"))
    ids = sorted(h["id"] for h in body["hearings"])
    assert ids == expected_ids(db, "2026-10-14", "2026-11-13")
    assert len({h["caseId"] for h in body["hearings"]}) >= 2  # more than one case
    assert body["truncated"] is False
    dates = [h["date"] for h in body["hearings"]]
    assert dates == sorted(dates)


@pytest.mark.parametrize("role", ["lead", "associate", "paralegal"])
def test_others_see_only_hearings_of_their_cases(as_: As, role: str) -> None:
    mine = add(as_("lead"), "2026-10-20", "Mention")
    body = schedule(as_(role), **{"from": "2026-01-01", "to": "2026-12-31"})
    assert {h["caseId"] for h in body["hearings"]} == {str(SATTVIK)}
    assert mine in {h["id"] for h in body["hearings"]}


def test_an_unrelated_advocate_never_sees_them(as_: As) -> None:
    mine = add(as_("lead"), "2026-10-20", "Mention")
    body = schedule(as_("other_advocate"), **{"from": "2026-01-01", "to": "2026-12-31"})
    assert str(SATTVIK) not in {h["caseId"] for h in body["hearings"]}
    assert mine not in {h["id"] for h in body["hearings"]}
    assert schedule(as_("other_paralegal"))["hearings"] == []


def test_each_entry_names_the_case_and_its_lead(as_: As) -> None:
    add(as_("lead"), "2026-10-20", "Mention", "09:45")
    entry = next(h for h in schedule(as_("lead"))["hearings"] if h["purpose"] == "Mention")
    assert entry["leadAttorney"] == "Aryan Goyal"
    assert entry["caseNumber"] and entry["caseTitle"]
    assert (entry["time"], entry["court"], entry["status"]) == (
        "09:45",
        "Court Room 7",
        "Scheduled",
    )


def test_cancelled_hearings_only_when_asked(as_: As) -> None:
    gone = add(as_("lead"), "2026-10-21", "Adjourned mention")
    as_("lead").post(f"/api/hearings/{gone}/cancel", json={"reason": "Not sitting."})
    assert gone not in {h["id"] for h in schedule(as_("lead"))["hearings"]}
    with_cancelled = schedule(as_("lead"), includeCancelled="true")["hearings"]
    entry = next(h for h in with_cancelled if h["id"] == gone)
    assert (entry["status"], entry["cancellationReason"]) == ("Cancelled", "Not sitting.")


def test_archived_cases_are_left_out(as_: As) -> None:
    mine = add(as_("lead"), "2026-10-20", "Mention")
    as_("admin").post(f"/api/cases/{SATTVIK}/archive")
    assert mine not in {h["id"] for h in schedule(as_("admin"))["hearings"]}


def test_past_ranges_are_allowed(as_: As, db: Session) -> None:
    body = schedule(as_("admin"), **{"from": "2026-09-01", "to": "2026-09-30"})
    assert sorted(h["id"] for h in body["hearings"]) == expected_ids(db, "2026-09-01", "2026-09-30")
    assert body["hearings"], "the sample data has hearings in September 2026"


def test_a_long_list_says_it_was_cut_short(as_: As) -> None:
    for day in ("2026-10-20", "2026-10-21", "2026-10-22"):
        add(as_("lead"), day, f"Hearing {day}")
    body = schedule(as_("lead"), limit=2)
    assert len(body["hearings"]) == 2 and body["truncated"] is True


@pytest.mark.parametrize(
    ("params", "message"),
    [
        (
            {"from": "2026-10-14", "to": "2026-10-13"},
            "The end date must be on or after the start date.",
        ),
        ({"from": "2026-01-01", "to": "2027-06-01"}, "Choose a range of at most a year."),
    ],
)
def test_ranges_are_checked(as_: As, params: dict[str, str], message: str) -> None:
    response = as_("admin").get("/api/hearings", params=params)
    assert response.status_code == 422
    assert response.json()["errors"] == [{"field": "to", "message": message}]


def test_malformed_dates_and_limits_are_refused(as_: As) -> None:
    assert as_("admin").get("/api/hearings", params={"from": "14/10/2026"}).status_code == 422
    assert as_("admin").get("/api/hearings", params={"limit": 0}).status_code == 422
    assert as_("admin").get("/api/hearings", params={"limit": 501}).status_code == 422
