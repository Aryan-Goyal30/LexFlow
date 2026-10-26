"""Deleting, restoring and purging documents (fixtures: access_fixtures).

Deleting in the app is soft: the document leaves the case but its record and
file are kept until an Administrator or the lead advocate restores it, or an
operator purges it from the command line.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from lexflow.models import AuditEvent, Document, User
from lexflow.services import documents as service
from lexflow.storage import LocalDiskStorage
from tests.access_fixtures import SATTVIK

PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
OTHER_PDF = b"%PDF-1.4\n% a different file\n%%EOF\n"

As = Callable[[str], TestClient]


def upload(http: TestClient, name: str = "Rejoinder.pdf", content: bytes = PDF) -> dict[str, Any]:
    response = http.post(
        f"/api/cases/{SATTVIK}/documents", files={"file": (name, content, "application/pdf")}
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def live_ids(http: TestClient) -> set[str]:
    return {d["id"] for d in http.get(f"/api/cases/{SATTVIK}").json()["documents"]}


def stored_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file() and ".staging" not in p.parts]


def audit_actions(db: Session) -> list[str]:
    return list(db.scalars(select(AuditEvent.action).order_by(AuditEvent.occurred_at)))


# --- who may do what -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "delete", "listing", "restore"),
    [
        ("admin", 204, 200, 200),
        ("lead", 204, 200, 200),
        ("associate", 403, 403, 403),
        ("paralegal", 403, 403, 403),
        ("other_advocate", 404, 404, 404),
    ],
)
def test_only_the_administrator_or_lead_delete_and_restore(
    as_: As, storage_root: Path, role: str, delete: int, listing: int, restore: int
) -> None:
    kept = upload(as_("lead"), "Kept.pdf")
    deleted = upload(as_("lead"), "Deleted.pdf", OTHER_PDF)
    assert as_("lead").delete(f"/api/documents/{deleted['id']}").status_code == 204

    assert as_(role).delete(f"/api/documents/{kept['id']}").status_code == delete
    assert as_(role).get(f"/api/cases/{SATTVIK}/documents/deleted").status_code == listing
    assert as_(role).post(f"/api/documents/{deleted['id']}/restore").status_code == restore


def test_the_uploader_and_the_deleter_are_recorded(
    as_: As, storage_root: Path, people: dict[str, User]
) -> None:
    created = upload(as_("paralegal"))
    assert created["uploadedBy"] == {
        "id": str(people["paralegal"].id),
        "name": "Assigned Paralegal",
    }
    as_("lead").delete(f"/api/documents/{created['id']}")

    listing = as_("lead").get(f"/api/cases/{SATTVIK}/documents/deleted").json()
    assert [d["id"] for d in listing] == [created["id"]]
    assert listing[0]["deletedBy"] == {"id": str(people["lead"].id), "name": "Aryan Goyal"}
    assert listing[0]["deletedAt"]
    assert listing[0]["uploadedBy"]["name"] == "Assigned Paralegal"


# --- delete and restore ------------------------------------------------------------------


def test_restoring_brings_back_the_same_file(as_: As, db: Session, storage_root: Path) -> None:
    created = upload(as_("lead"))
    as_("lead").delete(f"/api/documents/{created['id']}")
    assert created["id"] not in live_ids(as_("lead"))
    assert len(stored_files(storage_root)) == 1  # the file is kept

    restored = as_("admin").post(f"/api/documents/{created['id']}/restore")
    assert restored.status_code == 200
    assert restored.json()["id"] == created["id"]
    assert created["id"] in live_ids(as_("lead"))
    download = as_("lead").get(created["downloadUrl"])
    assert download.status_code == 200 and download.content == PDF
    assert as_("lead").get(f"/api/cases/{SATTVIK}/documents/deleted").json() == []

    row = db.get(Document, uuid.UUID(created["id"]))
    assert row is not None
    db.refresh(row)
    assert row.deleted_at is None and row.deleted_by_id is None
    assert audit_actions(db).count("document.deleted") == 1
    assert audit_actions(db).count("document.restored") == 1


def test_restoring_a_live_document_changes_nothing(
    as_: As, db: Session, storage_root: Path
) -> None:
    created = upload(as_("lead"))
    assert as_("lead").post(f"/api/documents/{created['id']}/restore").status_code == 200
    assert "document.restored" not in audit_actions(db)


def test_a_deleted_name_can_be_reused_and_restoring_then_waits_for_it(
    as_: As, storage_root: Path
) -> None:
    first = upload(as_("lead"), "Reply.pdf")
    as_("lead").delete(f"/api/documents/{first['id']}")
    second = upload(as_("lead"), "reply.PDF", OTHER_PDF)  # same name, any case

    clash = as_("lead").post(f"/api/documents/{first['id']}/restore")
    assert clash.status_code == 409
    assert clash.json()["code"] == "duplicate"
    assert "Delete or rename it, then restore" in clash.json()["detail"]

    as_("lead").delete(f"/api/documents/{second['id']}")
    assert as_("lead").post(f"/api/documents/{first['id']}/restore").status_code == 200
    assert live_ids(as_("lead")) >= {first["id"]}
    assert second["id"] not in live_ids(as_("lead"))


def test_a_deleted_document_is_not_found_anywhere_else(as_: As, storage_root: Path) -> None:
    created = upload(as_("lead"))
    as_("lead").delete(f"/api/documents/{created['id']}")
    listing = as_("lead").get(f"/api/cases/{SATTVIK}/documents").json()
    assert created["id"] not in {d["id"] for d in listing}
    for role in ("admin", "lead", "paralegal"):
        response = as_(role).get(created["downloadUrl"])
        assert response.status_code == 404, role
        assert response.json()["code"] == "document-not-found"


def test_on_an_archived_case_nothing_is_deleted_or_restored(as_: As, storage_root: Path) -> None:
    kept = upload(as_("lead"), "Kept.pdf")
    gone = upload(as_("lead"), "Gone.pdf", OTHER_PDF)
    as_("lead").delete(f"/api/documents/{gone['id']}")
    assert as_("admin").post(f"/api/cases/{SATTVIK}/archive").status_code == 200

    for response in (
        as_("admin").delete(f"/api/documents/{kept['id']}"),
        as_("admin").post(f"/api/documents/{gone['id']}/restore"),
    ):
        assert response.status_code == 409
        assert response.json()["code"] == "case-archived"
    # What was deleted can still be reviewed.
    listing = as_("lead").get(f"/api/cases/{SATTVIK}/documents/deleted")
    assert listing.status_code == 200
    assert [d["id"] for d in listing.json()] == [gone["id"]]


def test_a_document_on_a_case_you_cannot_see_is_not_found_even_when_deleted(
    as_: As, storage_root: Path
) -> None:
    created = upload(as_("lead"))
    as_("lead").delete(f"/api/documents/{created['id']}")
    response = as_("other_advocate").post(f"/api/documents/{created['id']}/restore")
    assert response.status_code == 404
    assert response.json()["code"] == "document-not-found"


# --- purging (the service behind the operator command) ------------------------------------


def test_purge_removes_only_deleted_documents(as_: As, db: Session, storage_root: Path) -> None:
    live = upload(as_("lead"), "Live.pdf")
    gone = upload(as_("lead"), "Gone.pdf", OTHER_PDF)
    as_("lead").delete(f"/api/documents/{gone['id']}")
    storage = LocalDiskStorage(storage_root)
    assert len(stored_files(storage_root)) == 2

    assert service.purge(db, storage, uuid.UUID(live["id"])) is False
    assert service.purge(db, storage, uuid.UUID(gone["id"])) is True

    assert db.get(Document, uuid.UUID(live["id"])) is not None
    assert db.get(Document, uuid.UUID(gone["id"])) is None
    assert len(stored_files(storage_root)) == 1
    download = as_("lead").get(live["downloadUrl"])
    assert download.status_code == 200 and download.content == PDF


def test_restoring_waits_while_the_same_content_is_on_the_case_under_another_name(
    as_: As, storage_root: Path
) -> None:
    first = upload(as_("lead"), "Reply.pdf")
    as_("lead").delete(f"/api/documents/{first['id']}")
    second = upload(as_("lead"), "Reply (copy).pdf")  # same content, new name: allowed now
    clash = as_("lead").post(f"/api/documents/{first['id']}/restore")
    assert (clash.status_code, clash.json()["code"]) == (409, "duplicate-content")
    assert "Reply (copy).pdf" in clash.json()["detail"]
    as_("lead").delete(f"/api/documents/{second['id']}")
    assert as_("lead").post(f"/api/documents/{first['id']}/restore").status_code == 200
