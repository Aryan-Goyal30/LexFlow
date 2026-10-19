"""Who may see and do what on cases, documents, hearings and reference data.

Six people stand in different relationships to the sample case "Sattvik Foods"
(case-1005, led by the sample advocate Aryan Goyal):

- admin: an Administrator (every case);
- lead: Aryan Goyal, its lead advocate;
- associate: an Advocate on its team;
- paralegal: a Paralegal assigned to it;
- other_advocate: Rajat Deshpande, who leads a different case;
- other_paralegal: a Paralegal assigned to nothing.

Lists are compared as sets of ids (not counts), and every refused change is
checked to have changed nothing.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lexflow.auth import sessions
from lexflow.config import get_settings
from lexflow.models import AuditEvent, Case, CaseMember, Client, TimelineEvent, User
from lexflow.seed import sample_uuid
from lexflow.seed.loader import load_sample_data, read_sample_data
from tests.conftest import http_client, make_user
from tests.test_cases import new_case

DATA = read_sample_data()
SATTVIK = sample_uuid("case", "case-1005")
ALL_CASES = {sample_uuid("case", c["legacyId"]) for c in DATA["cases"]}
RAJAT_CASES = {
    sample_uuid("case", c["legacyId"])
    for c in DATA["cases"]
    if c["leadAdvocate"] == "Rajat Deshpande"
}
PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"

ROLES = ("admin", "lead", "associate", "paralegal", "other_advocate", "other_paralegal")
ON_CASE = {"admin", "lead", "associate", "paralegal"}


def case_row(db: Session) -> tuple[Any, ...]:
    db.expire_all()
    case = db.get(Case, SATTVIK)
    assert case is not None
    return (
        case.status,
        case.title,
        case.court_name,
        case.lead_advocate_id,
        case.client_id,
        case.priority,
    )


def timeline_count(db: Session) -> int:
    return (
        db.scalar(
            select(func.count()).select_from(TimelineEvent).where(TimelineEvent.case_id == SATTVIK)
        )
        or 0
    )


# --- seeing cases ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("admin", ALL_CASES),
        ("lead", {SATTVIK}),
        ("associate", {SATTVIK}),
        ("paralegal", {SATTVIK}),
        ("other_advocate", RAJAT_CASES),
        ("other_paralegal", set()),
    ],
)
def test_the_case_list_holds_exactly_the_cases_one_may_see(
    as_: Callable[[str], TestClient], role: str, expected: set[uuid.UUID]
) -> None:
    response = as_(role).get("/api/cases")
    assert response.status_code == 200
    assert {uuid.UUID(c["id"]) for c in response.json()} == expected


@pytest.mark.parametrize("role", ROLES)
def test_opening_a_case_one_may_not_see_is_a_plain_not_found(
    as_: Callable[[str], TestClient], role: str
) -> None:
    for path in (f"/api/cases/{SATTVIK}", f"/api/cases/{SATTVIK}/documents"):
        response = as_(role).get(path)
        if role in ON_CASE:
            assert response.status_code == 200, (role, path)
        else:
            # The same answer as for a case that does not exist.
            assert response.status_code == 404, (role, path)
            assert response.json()["code"] == "case-not-found"
            missing = as_(role).get(path.replace(str(SATTVIK), str(uuid.uuid4())))
            assert missing.json() == response.json()


def test_refused_lookups_are_audited(
    as_: Callable[[str], TestClient], db: Session, people: dict[str, User]
) -> None:
    as_("other_advocate").get(f"/api/cases/{SATTVIK}")
    events = db.scalars(select(AuditEvent).where(AuditEvent.action == "access.denied")).all()
    assert [(e.actor_id, e.case_id, e.outcome) for e in events] == [
        (people["other_advocate"].id, SATTVIK, "denied")
    ]


@pytest.mark.parametrize("role", ROLES)
def test_upcoming_hearings_only_come_from_visible_cases(
    as_: Callable[[str], TestClient], role: str
) -> None:
    visible = {uuid.UUID(c["id"]) for c in as_(role).get("/api/cases").json()}
    hearings = as_(role).get("/api/hearings/upcoming?limit=50").json()
    assert {uuid.UUID(h["caseId"]) for h in hearings} <= visible
    if role == "admin":
        assert hearings  # the sample data has upcoming hearings to leak, if scoping failed


def test_permissions_in_the_case_detail_match_the_relationship(
    as_: Callable[[str], TestClient],
) -> None:
    def perms(role: str) -> dict[str, Any]:
        result: dict[str, Any] = as_(role).get(f"/api/cases/{SATTVIK}").json()["permissions"]
        return result

    assert perms("admin")["relation"] == "admin" and perms("admin")["canArchive"]
    lead = perms("lead")
    assert lead["relation"] == "lead"
    assert "leadAdvocateId" not in lead["editableFields"] and lead["canManageTeam"]
    associate = perms("associate")
    assert associate["canChangeStatus"] and not associate["canDeleteDocuments"]
    paralegal = perms("paralegal")
    assert sorted(paralegal["editableFields"]) == ["courtName", "opposingParty"]
    assert not paralegal["canChangeStatus"] and paralegal["canManageHearings"]
    assert paralegal["canUploadDocuments"] and not paralegal["canDeleteDocuments"]


# --- changing cases: every field needs its own permission --------------------------


def _patch_cases() -> list[Any]:
    other_client = str(sample_uuid("client", "c-002"))
    statuses = {
        "admin": 200, "lead": 200, "associate": 200, "paralegal": 403,
        "other_advocate": 404, "other_paralegal": 404,
    }  # fmt: skip
    listing = {**statuses, "paralegal": 200}
    admin_only = {**statuses, "lead": 403, "associate": 403}
    rows = []
    for role in ROLES:
        rows.append(pytest.param(role, {"status": "On Hold"}, statuses[role], id=f"status-{role}"))
        rows.append(
            pytest.param(role, {"title": "Renamed matter"}, statuses[role], id=f"title-{role}")
        )
        rows.append(
            pytest.param(role, {"courtName": "Court Room 9"}, listing[role], id=f"court-{role}")
        )
        rows.append(
            pytest.param(role, {"clientId": other_client}, admin_only[role], id=f"client-{role}")
        )
    return rows


@pytest.mark.parametrize(("role", "change", "expected"), _patch_cases())
def test_case_changes_follow_the_permission_matrix(
    as_: Callable[[str], TestClient],
    db: Session,
    role: str,
    change: dict[str, str],
    expected: int,
) -> None:
    before, entries = case_row(db), timeline_count(db)

    response = as_(role).patch(f"/api/cases/{SATTVIK}", json=change)

    assert response.status_code == expected, response.text
    if expected == 200:
        assert case_row(db) != before
        assert timeline_count(db) == entries + 1
    else:
        assert case_row(db) == before  # nothing at all changed
        assert timeline_count(db) == entries
        if expected == 403:
            assert response.json()["code"] in {"forbidden", "field-not-permitted"}


@pytest.mark.parametrize("role", ["lead", "associate", "paralegal"])
def test_nobody_but_an_administrator_can_change_the_lead(
    as_: Callable[[str], TestClient], db: Session, people: dict[str, User], role: str
) -> None:
    before = case_row(db)
    # Not even to themselves, and not even bundled with a field they may change.
    response = as_(role).patch(
        f"/api/cases/{SATTVIK}",
        json={"leadAdvocateId": str(people[role].id), "courtName": "Court Room 9"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "field-not-permitted"
    assert [e["field"] for e in response.json()["errors"]] == ["leadAdvocateId"]
    assert case_row(db) == before


def test_a_refused_field_is_refused_even_when_unchanged(
    as_: Callable[[str], TestClient], people: dict[str, User]
) -> None:
    response = as_("associate").patch(
        f"/api/cases/{SATTVIK}", json={"leadAdvocateId": str(people["lead"].id)}
    )
    assert response.status_code == 403


def test_an_administrator_changes_the_lead_and_the_new_lead_leaves_the_team(
    as_: Callable[[str], TestClient], db: Session, people: dict[str, User]
) -> None:
    response = as_("admin").patch(
        f"/api/cases/{SATTVIK}", json={"leadAdvocateId": str(people["associate"].id)}
    )
    assert response.status_code == 200
    assert db.get(CaseMember, (SATTVIK, people["associate"].id)) is None
    # The former lead no longer sees the case; the new lead does.
    assert as_("lead").get(f"/api/cases/{SATTVIK}").status_code == 404
    assert as_("associate").get(f"/api/cases/{SATTVIK}").json()["permissions"]["relation"] == "lead"


def test_moving_a_case_to_another_client_is_for_administrators_and_is_audited(
    as_: Callable[[str], TestClient], db: Session
) -> None:
    other_client = sample_uuid("client", "c-002")
    response = as_("admin").patch(f"/api/cases/{SATTVIK}", json={"clientId": str(other_client)})
    assert response.status_code == 200
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "case.updated")).one()
    assert event.details["fields"] == ["clientId"] and event.case_id == SATTVIK


# --- creating cases ------------------------------------------------------------------


def test_an_administrator_may_open_a_case_for_any_active_advocate(
    as_: Callable[[str], TestClient],
) -> None:
    lead = str(sample_uuid("advocate", "Meera Nair"))
    response = as_("admin").post("/api/cases", json=new_case(leadAdvocateId=lead))
    assert response.status_code == 201, response.text


def test_an_advocate_opens_cases_only_with_themselves_as_lead(
    as_: Callable[[str], TestClient], db: Session, people: dict[str, User]
) -> None:
    me = str(people["other_advocate"].id)
    mine = as_("other_advocate").post("/api/cases", json=new_case(leadAdvocateId=me))
    assert mine.status_code == 201
    assert mine.json()["permissions"]["relation"] == "lead"

    count = db.scalar(select(func.count()).select_from(Case))
    someone_else = as_("other_advocate").post(
        "/api/cases", json=new_case(leadAdvocateId=str(people["lead"].id))
    )
    assert someone_else.status_code == 403
    assert someone_else.json()["code"] == "field-not-permitted"
    assert db.scalar(select(func.count()).select_from(Case)) == count  # nothing created


@pytest.mark.parametrize("role", ["paralegal", "other_paralegal"])
def test_paralegals_do_not_open_cases(
    as_: Callable[[str], TestClient], people: dict[str, User], role: str
) -> None:
    response = as_(role).post("/api/cases", json=new_case(leadAdvocateId=str(people["lead"].id)))
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_a_deactivated_advocate_cannot_be_made_lead(
    as_: Callable[[str], TestClient], db: Session
) -> None:
    retired = make_user(db, role="Advocate", is_active=False)
    response = as_("admin").post("/api/cases", json=new_case(leadAdvocateId=str(retired.id)))
    assert response.status_code == 422
    assert [e["field"] for e in response.json()["errors"]] == ["leadAdvocateId"]


# --- documents -------------------------------------------------------------------------


def _upload(http: TestClient, name: str = "Brief.pdf") -> Any:
    return http.post(
        f"/api/cases/{SATTVIK}/documents", files={"file": (name, PDF, "application/pdf")}
    )


@pytest.mark.parametrize("role", ROLES)
def test_who_may_upload(as_: Callable[[str], TestClient], role: str, storage_root: Any) -> None:
    response = _upload(as_(role), f"Upload by {role}.pdf")
    if role in ON_CASE:
        assert response.status_code == 201, response.text
    else:
        assert response.status_code == 404
        assert response.json()["code"] == "case-not-found"
        stored = [p for p in storage_root.rglob("*") if p.is_file() and ".staging" not in p.parts]
        assert stored == []  # nothing was written for a refused upload


@pytest.mark.parametrize("role", ROLES)
def test_who_may_download_and_delete(as_: Callable[[str], TestClient], role: str) -> None:
    created = _upload(as_("admin")).json()
    download = as_(role).get(f"/api/documents/{created['id']}/download")
    delete = as_(role).delete(f"/api/documents/{created['id']}")

    if role in ON_CASE:
        assert download.status_code == 200 and download.content == PDF
    else:
        assert download.status_code == 404
        assert download.json()["code"] == "document-not-found"  # same as no such document
    expected_delete = {"admin": 204, "lead": 204, "associate": 403, "paralegal": 403}
    assert delete.status_code == expected_delete.get(role, 404), delete.text


def test_downloads_are_audited(
    as_: Callable[[str], TestClient], db: Session, people: dict[str, User]
) -> None:
    created = _upload(as_("admin")).json()
    as_("paralegal").get(f"/api/documents/{created['id']}/download")
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "document.downloaded")).one()
    assert (event.actor_id, event.target_id, event.case_id) == (
        people["paralegal"].id,
        uuid.UUID(created["id"]),
        SATTVIK,
    )


# --- reference data ----------------------------------------------------------------------


def test_client_records_are_scoped_but_the_picker_lists_everyone(
    as_: Callable[[str], TestClient],
) -> None:
    def ids(role: str, path: str) -> set[str]:
        return {c["id"] for c in as_(role).get(path).json()}

    every_client = {str(sample_uuid("client", c["legacyId"])) for c in DATA["clients"]}
    sattvik_client = {str(sample_uuid("client", "c-005"))}
    assert ids("admin", "/api/clients") == every_client
    assert ids("lead", "/api/clients") == sattvik_client
    assert ids("paralegal", "/api/clients") == sattvik_client
    assert ids("other_paralegal", "/api/clients") == set()

    # The new-case picker: names only, for those who may open cases.
    assert ids("other_advocate", "/api/clients/options") == every_client
    option = as_("other_advocate").get("/api/clients/options").json()[0]
    assert set(option) == {"id", "name", "isSample"}
    assert as_("paralegal").get("/api/clients/options").status_code == 403


def test_the_advocate_directory_lists_active_advocates_for_staff(
    as_: Callable[[str], TestClient], db: Session
) -> None:
    make_user(db, role="Advocate", name="Retired Advocate", is_active=False)
    names = {a["name"] for a in as_("other_paralegal").get("/api/advocates").json()}
    assert "Aryan Goyal" in names and "Associate Advocate" in names
    assert "Retired Advocate" not in names


# --- clients are not staff --------------------------------------------------------------


def test_a_client_session_cannot_use_staff_routes(app: FastAPI, db: Session) -> None:
    """Defence in depth: even with a session (clients cannot sign in yet), staff routes refuse."""
    load_sample_data(db)
    client_row = db.get(Client, sample_uuid("client", "c-005"))  # owns the Sattvik case
    assert client_row is not None
    user = make_user(db, role="Client", client_id=client_row.id)
    token = sessions.start(
        db, user, now=datetime.now(UTC), settings=get_settings(), user_agent=None
    )
    db.commit()
    with http_client(
        app, raise_server_exceptions=False, cookies={"lexflow_session": token}
    ) as http:
        for path in ("/api/cases", f"/api/cases/{SATTVIK}", "/api/clients", "/api/advocates"):
            response = http.get(path)
            assert response.status_code == 403, path
            assert response.json()["code"] == "forbidden"
