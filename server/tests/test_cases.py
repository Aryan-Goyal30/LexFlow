"""Cases API: list, detail, create, update, upcoming hearings, numbering, errors."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator
from datetime import date, time
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from lexflow.clock import get_today
from lexflow.models import Case, CaseNumberCounter, Client, Hearing, TimelineEvent, User
from lexflow.seed import sample_uuid
from lexflow.seed.loader import load_sample_data, read_sample_data
from lexflow.services.case_numbers import allocate_case_number

TODAY = date(2026, 10, 14)
DATA = read_sample_data()
SATTVIK = str(sample_uuid("case", "case-1005"))
MEERA = str(sample_uuid("advocate", "Meera Nair"))
CLIENT_3 = str(sample_uuid("client", "c-003"))


@pytest.fixture
def seeded(db: Session, app: FastAPI) -> Session:
    load_sample_data(db)
    app.dependency_overrides[get_today] = lambda: TODAY
    return db


def new_case(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": "Test Matter v. Other Party",
        "clientId": CLIENT_3,
        "practiceArea": "Civil",
        "status": "Open",
        "priority": "Medium",
        "leadAdvocateId": MEERA,
        "courtName": "Test Court",
        "opposingParty": "Other Party",
        "description": "A summary long enough to pass validation.",
        "nextHearing": "2026-11-20",
    }
    body.update(overrides)
    return body


def field_errors(response: Any) -> dict[str, str]:
    assert response.status_code == 422, response.text
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["code"] == "validation-error"
    return {e["field"]: e["message"] for e in body["errors"]}


# --- list -----------------------------------------------------------------------


def test_list_is_empty_without_data(client: TestClient) -> None:
    assert client.get("/api/cases").json() == []


def test_list_returns_summaries_with_derived_fields(client: TestClient, seeded: Session) -> None:
    response = client.get("/api/cases")

    assert response.status_code == 200
    summaries = response.json()
    assert len(summaries) == len(DATA["cases"])
    by_number = {s["caseNumber"]: s for s in summaries}
    for source in DATA["cases"]:
        summary = by_number[source["caseNumber"]]
        assert summary["id"] == str(sample_uuid("case", source["legacyId"]))
        assert summary["clientName"] == source["clientName"]
        assert summary["leadAttorney"] == source["leadAdvocate"]
        assert summary["documentCount"] == len(source["documents"])
        # Derived from the hearings, and equal to what the sample data showed.
        assert summary["nextHearing"] == source["expectedNextHearing"]
        assert summary["isSample"] is True
        assert "description" not in summary and "documents" not in summary
    opened = [s["openedOn"] for s in summaries]
    assert opened == sorted(opened, reverse=True)


def test_next_hearing_prefers_upcoming_then_latest_past(
    client: TestClient, seeded: Session
) -> None:
    case_id = sample_uuid("case", "case-1005")
    seeded.add_all(
        [
            Hearing(case_id=case_id, hearing_date=date(2026, 12, 1), court="C", purpose="Later"),
            Hearing(case_id=case_id, hearing_date=date(2026, 10, 20), court="C", purpose="Soon"),
            Hearing(case_id=case_id, hearing_date=date(2026, 8, 1), court="C", purpose="Past"),
        ]
    )
    seeded.flush()

    summary = next(s for s in client.get("/api/cases").json() if s["id"] == SATTVIK)
    assert summary["nextHearing"] == "2026-10-20"

    # The sample hearing of case-1001 (2026-09-22) is past: it is still shown.
    aarav = next(s for s in client.get("/api/cases").json() if s["caseNumber"] == "LF-2026-0142")
    assert aarav["nextHearing"] == "2026-09-22"


# --- detail ---------------------------------------------------------------------


def test_detail_includes_ordered_children(client: TestClient, seeded: Session) -> None:
    response = client.get(f"/api/cases/{SATTVIK}")

    assert response.status_code == 200
    detail = response.json()
    source = next(c for c in DATA["cases"] if c["legacyId"] == "case-1005")
    assert detail["description"] == source["description"]
    # Documents: newest first, same-day records by name.
    expected_documents = sorted(source["documents"], key=lambda d: d["name"].lower())
    expected_documents.sort(key=lambda d: d["uploadedOn"], reverse=True)
    assert [d["name"] for d in detail["documents"]] == [d["name"] for d in expected_documents]
    assert [t["label"] for t in detail["timeline"]] == [t["label"] for t in source["timeline"]]
    assert detail["hearings"] == [
        {
            "id": str(sample_uuid("hearing", "h-5")),
            "date": "2026-09-30",
            "time": "12:00",
            "court": "Court Room 26",
            "purpose": "Hearing on confirmation of the ad-interim injunction",
            "isSample": True,
        }
    ]
    for event in detail["timeline"]:
        assert event["actor"] is None
    document = detail["documents"][0]
    assert document["hasFile"] is False
    assert document["downloadUrl"] is None
    assert document["sizeBytes"] is None
    assert document["size"] == expected_documents[0]["sizeLabel"]


@pytest.mark.parametrize("case_id", [str(uuid.uuid4()), "case-1005", "not-a-uuid"])
def test_detail_unknown_id_is_404(client: TestClient, case_id: str) -> None:
    response = client.get(f"/api/cases/{case_id}")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "case-not-found"


# --- create ---------------------------------------------------------------------


def test_create_assigns_number_date_hearing_and_timeline(
    client: TestClient, seeded: Session
) -> None:
    response = client.post("/api/cases", json=new_case(title="  Spaced Out Title  "))

    assert response.status_code == 201, response.text
    created = response.json()
    assert response.headers["location"] == f"/api/cases/{created['id']}"
    assert created["caseNumber"] == "LF-2026-0490"  # after the highest sample number
    assert created["title"] == "Spaced Out Title"
    assert created["openedOn"] == TODAY.isoformat()
    assert created["clientName"] == "Vikram Chauhan"
    assert created["leadAttorney"] == "Meera Nair"
    assert created["isSample"] is False
    assert created["nextHearing"] == "2026-11-20"
    assert created["hearings"] == [
        {
            "id": created["hearings"][0]["id"],
            "date": "2026-11-20",
            "time": None,  # unknown until listed; never guessed
            "court": "To be notified",
            "purpose": "First listing",
            "isSample": False,
        }
    ]
    assert [(t["label"], t["actor"]) for t in created["timeline"]] == [("Matter opened", None)]
    assert created["documents"] == []

    listed = client.get("/api/cases").json()
    assert listed[0]["id"] == created["id"]


def test_create_without_optional_fields(client: TestClient, seeded: Session) -> None:
    body = new_case(courtName="   ", opposingParty="")
    del body["nextHearing"]

    created = client.post("/api/cases", json=body).json()

    assert created["courtName"] is None
    assert created["opposingParty"] is None
    assert created["hearings"] == []
    assert created["nextHearing"] is None


def test_create_reports_every_invalid_field(client: TestClient, seeded: Session) -> None:
    errors = field_errors(
        client.post(
            "/api/cases",
            json=new_case(title="ab", description="short", status="Pending", priority=None),
        )
    )

    assert errors["title"] == "Enter a descriptive case title (at least 4 characters)."
    assert errors["description"] == "Provide a short summary (at least 10 characters)."
    assert "status" in errors
    assert "priority" in errors


def test_create_rejects_missing_fields(client: TestClient, seeded: Session) -> None:
    errors = field_errors(client.post("/api/cases", json={}))

    assert {"title", "clientId", "description", "leadAdvocateId", "status"} <= set(errors)


def test_create_rejects_unknown_references(client: TestClient, seeded: Session) -> None:
    paralegal = User(name="A Paralegal", role="Paralegal")
    seeded.add(paralegal)
    seeded.flush()

    errors = field_errors(
        client.post(
            "/api/cases",
            json=new_case(clientId=str(uuid.uuid4()), leadAdvocateId=str(paralegal.id)),
        )
    )

    assert errors == {
        "clientId": "Select a client from the list.",
        "leadAdvocateId": "Select a lead advocate from the list.",
    }


def test_create_rejects_past_hearing_in_business_time_zone(
    client: TestClient, seeded: Session
) -> None:
    errors = field_errors(client.post("/api/cases", json=new_case(nextHearing="2026-10-13")))
    assert errors == {"nextHearing": "The next hearing date cannot be in the past."}

    today = client.post("/api/cases", json=new_case(nextHearing=TODAY.isoformat()))
    assert today.status_code == 201


def test_create_rejects_unknown_fields(client: TestClient, seeded: Session) -> None:
    errors = field_errors(client.post("/api/cases", json=new_case(caseNumber="LF-2026-9999")))
    assert "caseNumber" in errors


def test_create_rejects_malformed_json(client: TestClient, seeded: Session) -> None:
    response = client.post(
        "/api/cases", content=b"{not json", headers={"content-type": "application/json"}
    )
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"


def test_case_numbers_start_fresh_each_year(
    client: TestClient, seeded: Session, app: FastAPI
) -> None:
    app.dependency_overrides[get_today] = lambda: date(2027, 1, 2)

    first = client.post("/api/cases", json=new_case(nextHearing=None)).json()
    second = client.post("/api/cases", json=new_case(nextHearing=None)).json()

    assert (first["caseNumber"], second["caseNumber"]) == ("LF-2027-0001", "LF-2027-0002")


def test_first_number_of_a_year_skips_existing_numbers(seeded: Session) -> None:
    # A case imported without a counter row for its year.
    seeded.add(
        Case(
            case_number="LF-2030-0041",
            title="Imported matter",
            status="Open",
            priority="Low",
            practice_area="Civil",
            client_id=sample_uuid("client", "c-001"),
            lead_advocate_id=sample_uuid("advocate", "Meera Nair"),
            description="Imported without a counter row.",
            opened_on=date(2030, 1, 1),
        )
    )
    seeded.flush()

    assert allocate_case_number(seeded, 2030) == "LF-2030-0042"
    assert allocate_case_number(seeded, 2030) == "LF-2030-0043"


# --- update ---------------------------------------------------------------------


def test_update_changes_fields_and_records_timeline(client: TestClient, seeded: Session) -> None:
    response = client.patch(
        f"/api/cases/{SATTVIK}",
        json={"status": "On Hold", "priority": "Critical", "courtName": None, "title": "Renamed"},
    )

    assert response.status_code == 200, response.text
    updated = response.json()
    assert (updated["status"], updated["priority"], updated["title"]) == (
        "On Hold",
        "Critical",
        "Renamed",
    )
    assert updated["courtName"] is None
    last = updated["timeline"][-1]
    assert last["label"] == "Case details updated"
    assert last["actor"] is None  # no signed-in user exists in Phase 1
    assert "Status changed from In Progress to On Hold." in last["description"]
    assert "Priority changed from High to Critical." in last["description"]
    assert "Title updated." in last["description"]
    assert "Court updated." in last["description"]
    assert last["date"] == TODAY.isoformat()


def test_update_without_changes_records_nothing(client: TestClient, seeded: Session) -> None:
    before = client.get(f"/api/cases/{SATTVIK}").json()

    same = client.patch(f"/api/cases/{SATTVIK}", json={"status": before["status"]})
    empty = client.patch(f"/api/cases/{SATTVIK}", json={})

    assert same.status_code == empty.status_code == 200
    assert len(empty.json()["timeline"]) == len(before["timeline"])


def test_update_validation(client: TestClient, seeded: Session) -> None:
    assert "title" in field_errors(client.patch(f"/api/cases/{SATTVIK}", json={"title": None}))
    assert "status" in field_errors(client.patch(f"/api/cases/{SATTVIK}", json={"status": "Gone"}))
    assert "description" in field_errors(
        client.patch(f"/api/cases/{SATTVIK}", json={"description": "tiny"})
    )
    assert field_errors(
        client.patch(f"/api/cases/{SATTVIK}", json={"clientId": str(uuid.uuid4())})
    ) == {"clientId": "Select a client from the list."}
    assert "nextHearing" in field_errors(
        client.patch(f"/api/cases/{SATTVIK}", json={"nextHearing": "2027-01-01"})
    )


def test_update_unknown_case_is_404(client: TestClient, seeded: Session) -> None:
    response = client.patch(f"/api/cases/{uuid.uuid4()}", json={"status": "Closed"})

    assert response.status_code == 404
    assert response.json()["code"] == "case-not-found"


def test_update_can_change_client(client: TestClient, seeded: Session) -> None:
    response = client.patch(f"/api/cases/{SATTVIK}", json={"clientId": CLIENT_3})

    assert response.json()["clientName"] == "Vikram Chauhan"
    assert response.json()["timeline"][-1]["description"] == "Client updated."


# --- upcoming hearings -------------------------------------------------------------


def test_upcoming_hearings_from_today(client: TestClient, seeded: Session) -> None:
    response = client.get("/api/hearings/upcoming")

    assert response.status_code == 200
    hearings = response.json()
    # Only the sample hearing dated 2026-10-14 is on or after "today".
    assert [(h["date"], h["caseNumber"]) for h in hearings] == [("2026-10-14", "LF-2025-0331")]
    assert hearings[0]["caseTitle"] == "Suresh Iyer v. Lalitha Iyer and Others"
    assert hearings[0]["time"] == "11:00"


def test_upcoming_hearings_order_and_limit(
    client: TestClient, seeded: Session, app: FastAPI
) -> None:
    app.dependency_overrides[get_today] = lambda: date(2026, 1, 1)
    case_id = sample_uuid("case", "case-1005")
    seeded.add_all(
        [
            Hearing(case_id=case_id, hearing_date=date(2026, 9, 30), court="C", purpose="untimed"),
            Hearing(
                case_id=case_id,
                hearing_date=date(2026, 9, 30),
                hearing_time=time(9, 0),
                court="C",
                purpose="early",
            ),
        ]
    )
    seeded.flush()

    hearings = client.get("/api/hearings/upcoming", params={"limit": 50}).json()
    dates = [h["date"] for h in hearings]
    assert dates == sorted(dates)
    same_day = [h["purpose"] for h in hearings if h["date"] == "2026-09-30"]
    assert same_day[0] == "early" and same_day[-1] == "untimed"

    assert len(client.get("/api/hearings/upcoming", params={"limit": 2}).json()) == 2
    for bad in (0, 51, "x"):
        assert "limit" in field_errors(client.get("/api/hearings/upcoming", params={"limit": bad}))


# --- database constraints -----------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [("status", "Pending"), ("priority", "Urgent"), ("practice_area", "Tax"), ("title", "ab")],
)
def test_database_rejects_invalid_case_values(seeded: Session, field: str, value: str) -> None:
    case = seeded.get(Case, sample_uuid("case", "case-1005"))
    assert case is not None
    setattr(case, field, value)
    with pytest.raises(IntegrityError):
        seeded.flush()


def test_database_rejects_duplicate_case_numbers(seeded: Session) -> None:
    duplicate = Case(
        case_number="LF-2026-0142",
        title="Duplicate number",
        status="Open",
        priority="Low",
        practice_area="Civil",
        client_id=sample_uuid("client", "c-001"),
        lead_advocate_id=sample_uuid("advocate", "Meera Nair"),
        description="Should be rejected by the unique constraint.",
        opened_on=TODAY,
    )
    seeded.add(duplicate)
    with pytest.raises(IntegrityError):
        seeded.flush()


def test_database_blocks_deleting_a_client_with_cases(seeded: Session) -> None:
    client_row = seeded.get(Client, sample_uuid("client", "c-001"))
    seeded.delete(client_row)
    with pytest.raises(IntegrityError):
        seeded.flush()


# --- concurrency (real commits) ---------------------------------------------------


@pytest.fixture
def committed_reference(committed_engine: Engine) -> Iterator[tuple[uuid.UUID, uuid.UUID]]:
    with Session(committed_engine) as session, session.begin():
        client_row = Client(name="Concurrent Client", email="c@example.invalid", phone="0")
        advocate = User(name="Concurrent Advocate", role="Advocate")
        session.add_all([client_row, advocate])
        session.flush()
        ids = (client_row.id, advocate.id)
    yield ids


def test_concurrent_allocations_never_repeat(committed_engine: Engine) -> None:
    workers, results, errors = 12, [], []
    barrier = threading.Barrier(workers)

    def allocate() -> None:
        try:
            with Session(committed_engine) as session:
                barrier.wait()
                number = allocate_case_number(session, 2031)
                session.commit()
            results.append(number)
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(exc)

    threads = [threading.Thread(target=allocate) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert errors == []
    assert sorted(results) == [f"LF-2031-{n:04d}" for n in range(1, workers + 1)]


def test_concurrent_case_creation_through_the_api(
    committed_engine: Engine, committed_reference: tuple[uuid.UUID, uuid.UUID]
) -> None:
    from lexflow.main import create_app

    client_id, advocate_id = committed_reference
    app = create_app()  # real sessions: every request commits
    app.dependency_overrides[get_today] = lambda: TODAY
    workers, statuses, numbers = 8, [], []
    barrier = threading.Barrier(workers)

    def create() -> None:
        with TestClient(app) as http:
            barrier.wait()
            response = http.post(
                "/api/cases",
                json=new_case(clientId=str(client_id), leadAdvocateId=str(advocate_id)),
            )
        statuses.append(response.status_code)
        if response.status_code == 201:
            numbers.append(response.json()["caseNumber"])

    threads = [threading.Thread(target=create) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert statuses == [201] * workers
    assert sorted(numbers) == [f"LF-2026-{n:04d}" for n in range(1, workers + 1)]
    with Session(committed_engine) as session:
        counter = session.get(CaseNumberCounter, 2026)
        assert counter is not None and counter.last_value == workers
        events = session.scalars(select(TimelineEvent)).all()
        assert len(events) == workers
