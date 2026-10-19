"""Editing cases, status changes, archiving and case teams (fixtures: access_fixtures)."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from lexflow.models import AuditEvent, Case, CaseMember, Client, TimelineEvent, User
from lexflow.seed import sample_uuid
from lexflow.seed.loader import load_sample_data
from tests.access_fixtures import SATTVIK
from tests.conftest import committed_user, http_client, make_user, sign_in_as

PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"

As = Callable[[str], TestClient]


def timeline(http: TestClient) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = http.get(f"/api/cases/{SATTVIK}").json()["timeline"]
    return entries


def audit_actions(db: Session) -> list[str]:
    return list(db.scalars(select(AuditEvent.action).order_by(AuditEvent.occurred_at)))


# --- editing and status ---------------------------------------------------------------


def test_the_lead_edits_details_and_the_timeline_says_who_and_when(
    as_: As, db: Session, people: dict[str, User]
) -> None:
    response = as_("lead").patch(
        f"/api/cases/{SATTVIK}",
        json={"title": "Sattvik Foods v. Annapurna Snacks (amended)", "priority": "Critical"},
    )
    assert response.status_code == 200, response.text
    last = response.json()["timeline"][-1]
    assert last["label"] == "Case details updated"
    assert last["description"] == "Title updated. Priority changed from High to Critical."
    assert last["actor"] == {"id": str(people["lead"].id), "name": "Aryan Goyal"}
    assert last["recordedAt"]  # a timestamp, not just a date
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "case.updated")).one()
    assert event.details == {"fields": ["title", "priority"], "newPriority": "Critical"}


def test_status_can_close_and_reopen_a_case(as_: As) -> None:
    for status in ("Closed", "In Progress", "On Hold", "Open"):
        response = as_("associate").patch(f"/api/cases/{SATTVIK}", json={"status": status})
        assert response.status_code == 200
        assert response.json()["status"] == status


def test_changes_on_the_same_day_stay_in_the_order_they_were_made(as_: As) -> None:
    # The test database runs every request in one transaction, where now() is
    # fixed: entries must still come back in order (they are stamped in Python).
    sequence = ["Closed", "Open", "On Hold", "In Progress", "Closed", "Open"]
    for status in sequence:
        as_("lead").patch(f"/api/cases/{SATTVIK}", json={"status": status})
    recorded = [e["description"] for e in timeline(as_("lead"))[-len(sequence) :]]
    assert [d.removesuffix(".").rsplit(" to ", 1)[1] for d in recorded] == sequence


def test_an_unchanged_value_records_nothing(as_: As, db: Session) -> None:
    current = as_("lead").get(f"/api/cases/{SATTVIK}").json()
    before = len(current["timeline"])
    as_("lead").patch(f"/api/cases/{SATTVIK}", json={"status": current["status"]})
    assert len(timeline(as_("lead"))) == before
    assert "case.updated" not in audit_actions(db)


# --- archiving ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("admin", 200),
        ("lead", 403),
        ("associate", 403),
        ("paralegal", 403),
        ("other_advocate", 404),
    ],
)
def test_only_administrators_archive(as_: As, role: str, expected: int) -> None:
    assert as_(role).post(f"/api/cases/{SATTVIK}/archive").status_code == expected


def test_an_archived_case_is_kept_read_only_and_out_of_the_lists(
    as_: As, db: Session, people: dict[str, User]
) -> None:
    created = (
        as_("admin")
        .post(
            f"/api/cases/{SATTVIK}/documents", files={"file": ("Kept.pdf", PDF, "application/pdf")}
        )
        .json()
    )
    archived = as_("admin").post(f"/api/cases/{SATTVIK}/archive")
    assert archived.status_code == 200
    detail = archived.json()
    assert detail["archivedAt"] is not None
    assert detail["timeline"][-1]["label"] == "Case archived"
    # Everything is still there and still readable.
    assert any(d["id"] == created["id"] for d in detail["documents"])
    lead_view = as_("lead").get(f"/api/cases/{SATTVIK}")
    assert lead_view.status_code == 200
    assert lead_view.json()["permissions"]["editableFields"] == []
    download = as_("lead").get(f"/api/documents/{created['id']}/download")
    assert download.status_code == 200 and download.content == PDF

    # Hidden from default lists and from upcoming hearings; listed on request.
    def ids(path: str) -> set[str]:
        return {c["id"] for c in as_("admin").get(path).json()}

    assert str(SATTVIK) not in ids("/api/cases")
    assert str(SATTVIK) in ids("/api/cases?archived=include")
    assert ids("/api/cases?archived=only") == {str(SATTVIK)}
    upcoming = as_("admin").get("/api/hearings/upcoming?limit=50").json()
    assert str(SATTVIK) not in {h["caseId"] for h in upcoming}

    # Nothing may change, not even for an Administrator, until it is restored.
    attempts = {
        "edit": as_("admin").patch(f"/api/cases/{SATTVIK}", json={"status": "Closed"}),
        "upload": as_("lead").post(
            f"/api/cases/{SATTVIK}/documents",
            files={"file": ("Late.pdf", PDF, "application/pdf")},
        ),
        "delete": as_("lead").delete(f"/api/documents/{created['id']}"),
        "team": as_("lead").post(
            f"/api/cases/{SATTVIK}/team", json={"userId": str(people["other_paralegal"].id)}
        ),
    }
    for name, response in attempts.items():
        assert response.status_code == 409, name
        assert response.json()["code"] == "case-archived", name

    restored = as_("admin").post(f"/api/cases/{SATTVIK}/unarchive")
    assert restored.status_code == 200
    assert restored.json()["archivedAt"] is None
    assert restored.json()["timeline"][-1]["label"] == "Case restored"
    assert as_("lead").patch(f"/api/cases/{SATTVIK}", json={"status": "Closed"}).status_code == 200
    assert {"case.archived", "case.restored"} <= set(audit_actions(db))


def test_archiving_twice_records_it_once(as_: As) -> None:
    as_("admin").post(f"/api/cases/{SATTVIK}/archive")
    second = as_("admin").post(f"/api/cases/{SATTVIK}/archive").json()
    assert [e["label"] for e in second["timeline"]].count("Case archived") == 1


# --- case teams -------------------------------------------------------------------------


def test_the_lead_builds_the_team_and_members_gain_access(
    as_: As, db: Session, people: dict[str, User]
) -> None:
    newcomer = people["other_paralegal"]
    assert as_("other_paralegal").get(f"/api/cases/{SATTVIK}").status_code == 404

    added = as_("lead").post(f"/api/cases/{SATTVIK}/team", json={"userId": str(newcomer.id)})
    assert added.status_code == 200, added.text
    team = {m["name"]: m["memberRole"] for m in added.json()["team"]}
    assert team == {
        "Associate Advocate": "associate",
        "Assigned Paralegal": "paralegal",
        "Unassigned Paralegal": "paralegal",
    }
    assert added.json()["timeline"][-1]["description"] == (
        "Unassigned Paralegal joined the case team as a paralegal."
    )
    assert as_("other_paralegal").get(f"/api/cases/{SATTVIK}").status_code == 200

    removed = as_("lead").delete(f"/api/cases/{SATTVIK}/team/{newcomer.id}")
    assert removed.status_code == 200
    assert as_("other_paralegal").get(f"/api/cases/{SATTVIK}").status_code == 404
    assert audit_actions(db).count("case.team_member_added") == 1
    assert audit_actions(db).count("case.team_member_removed") == 1


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("admin", 200),
        ("lead", 200),
        ("associate", 403),
        ("paralegal", 403),
        ("other_advocate", 404),
    ],
)
def test_only_the_administrator_or_lead_change_the_team(
    as_: As, people: dict[str, User], role: str, expected: int
) -> None:
    newcomer = str(people["other_paralegal"].id)
    response = as_(role).post(f"/api/cases/{SATTVIK}/team", json={"userId": newcomer})
    assert response.status_code == expected


def test_team_members_must_be_active_advocates_or_paralegals(
    as_: As, db: Session, people: dict[str, User]
) -> None:
    client_row = db.get(Client, sample_uuid("client", "c-005"))
    assert client_row is not None
    candidates = {
        "inactive": make_user(db, role="Paralegal", is_active=False).id,
        "administrator": make_user(db, role="Administrator").id,
        "client": make_user(db, role="Client", client_id=client_row.id).id,
        "the lead": people["lead"].id,
        "nobody": uuid.uuid4(),
    }
    for name, user_id in candidates.items():
        response = as_("lead").post(f"/api/cases/{SATTVIK}/team", json={"userId": str(user_id)})
        assert response.status_code == 422, name
        assert [e["field"] for e in response.json()["errors"]] == ["userId"], name


def test_adding_a_member_twice_changes_nothing(
    as_: As, db: Session, people: dict[str, User]
) -> None:
    member = str(people["paralegal"].id)
    before = len(timeline(as_("lead")))
    assert (
        as_("lead").post(f"/api/cases/{SATTVIK}/team", json={"userId": member}).status_code == 200
    )
    assert len(timeline(as_("lead"))) == before
    count = db.scalars(select(CaseMember).where(CaseMember.case_id == SATTVIK)).all()
    assert len(count) == 2


def test_removing_someone_not_on_the_team_is_a_not_found(as_: As, people: dict[str, User]) -> None:
    response = as_("lead").delete(f"/api/cases/{SATTVIK}/team/{people['other_paralegal'].id}")
    assert response.status_code == 404
    assert response.json()["code"] == "member-not-found"


def test_the_staff_directory_lists_active_advocates_and_paralegals(as_: As, db: Session) -> None:
    make_user(db, role="Paralegal", name="Former Paralegal", is_active=False)
    staff = as_("paralegal").get("/api/staff").json()
    roles = {s["role"] for s in staff}
    names = {s["name"] for s in staff}
    assert roles == {"Advocate", "Paralegal"}
    assert "Former Paralegal" not in names and "Assigned Paralegal" in names
    assert set(staff[0]) == {"id", "name", "role"}  # no contact details


# --- no false audit entries when a change is rolled back --------------------------------


@pytest.fixture
def failing_commit_app(committed_engine: Engine) -> Iterator[tuple[FastAPI, str]]:
    from sqlalchemy.orm import sessionmaker

    from lexflow.db import get_session
    from lexflow.main import create_app

    with Session(committed_engine) as session, session.begin():
        load_sample_data(session)
    email = committed_user(committed_engine)

    class FailingCommit(Session):
        """Commits for sign-in, but fails when a case change is committed."""

        def commit(self) -> None:
            if any(isinstance(o, TimelineEvent) for o in self.new):
                self.rollback()
                raise RuntimeError("database went away")
            super().commit()

    app = create_app()
    factory = sessionmaker(bind=committed_engine, class_=FailingCommit, expire_on_commit=False)

    def session_dependency() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    yield app, email


def test_a_change_that_rolls_back_leaves_no_audit_claiming_it_happened(
    failing_commit_app: tuple[FastAPI, str], committed_engine: Engine
) -> None:
    app, email = failing_commit_app
    with http_client(app, raise_server_exceptions=False) as http:
        sign_in_as(http, email)
        response = http.patch(f"/api/cases/{SATTVIK}", json={"status": "Closed"})
    assert response.status_code == 500

    with Session(committed_engine) as session:
        case = session.get(Case, SATTVIK)
        assert case is not None and case.status != "Closed"
        actions = session.scalars(select(AuditEvent.action)).all()
        assert "case.updated" not in actions
        assert "auth.sign_in" in actions  # the audit log itself was working
