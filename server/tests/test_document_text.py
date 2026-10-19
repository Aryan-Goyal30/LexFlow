"""Reading extracted text and asking for a retry (fixtures: access_fixtures).

Anonymous callers and Client accounts are refused by the route sweeps in
``test_access_required.py`` and ``test_portal.py``, which cover these routes too.
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

from lexflow import worker
from lexflow.config import get_settings
from lexflow.extraction import Extracted, Limits, extract
from lexflow.models import AuditEvent, DocumentExtraction, User
from lexflow.seed import sample_uuid
from lexflow.storage import LocalDiskStorage
from tests.access_fixtures import SATTVIK
from tests.conftest import shared_sessions
from tests.document_fixtures import SAMPLE_PAGES, pdf_with_pages, pdf_without_text
from tests.test_documents import png_bytes

As = Callable[[str], TestClient]


def in_process(content_type: str, data: bytes, limits: Limits, timeout: float) -> Extracted:
    return extract(content_type, data, limits)


def upload(http: TestClient, name: str, content: bytes, ctype: str = "application/pdf") -> str:
    response = http.post(f"/api/cases/{SATTVIK}/documents", files={"file": (name, content, ctype)})
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def process(db: Session, root: Path) -> None:
    worker.run(
        shared_sessions(db),
        LocalDiskStorage(root),
        get_settings(),
        worker_id="test",
        once=True,
        extract=in_process,
    )


@pytest.fixture
def ready(as_: As, db: Session, storage_root: Path) -> str:
    document = upload(as_("lead"), "Petition.pdf", pdf_with_pages(SAMPLE_PAGES))
    process(db, storage_root)
    return document


def text(http: TestClient, document: str, section: int = 1) -> Any:
    return http.get(f"/api/documents/{document}/text", params={"section": section})


# --- reading --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("admin", 200),
        ("lead", 200),
        ("associate", 200),
        ("paralegal", 200),
        ("other_advocate", 404),
        ("other_paralegal", 404),
    ],
)
def test_staff_on_the_case_read_the_text(as_: As, ready: str, role: str, expected: int) -> None:
    response = text(as_(role), ready)
    assert response.status_code == expected
    if expected == 404:
        assert response.json()["code"] == "document-not-found"


def test_each_page_comes_back_with_its_number_and_exact_text(as_: As, ready: str) -> None:
    for number, page in enumerate(SAMPLE_PAGES, start=1):
        body = text(as_("paralegal"), ready, number).json()
        assert body["section"]["number"] == number
        assert body["section"]["pageNumber"] == number
        assert body["section"]["text"] == page
        assert body["section"]["chunkCount"] >= 1
    assert body["pageCount"] == 3 and body["sectionCount"] == 3
    assert body["documentName"] == "Petition.pdf"
    assert body["extractor"].startswith("pypdf ")


def test_pages_that_do_not_exist(as_: As, ready: str) -> None:
    beyond = text(as_("lead"), ready, 4)
    assert beyond.status_code == 404
    assert beyond.json()["code"] == "section-not-found"
    assert beyond.json()["detail"] == "This document has 3 pages."
    assert text(as_("lead"), ready, 0).status_code == 422


def test_reading_text_is_audited(as_: As, db: Session, ready: str, people: dict[str, User]) -> None:
    text(as_("paralegal"), ready, 2)
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "document.text_viewed")).one()
    assert event.actor_id == people["paralegal"].id
    assert str(event.target_id) == ready and event.case_id == SATTVIK
    assert event.details == {"section": 2}
    assert "petitioner" not in str(event.details)  # never the text itself


def test_text_is_not_available_until_it_is_ready_and_says_why(
    as_: As, db: Session, storage_root: Path
) -> None:
    waiting = upload(as_("lead"), "Waiting.pdf", pdf_with_pages(["FICTIONAL."]))
    response = text(as_("lead"), waiting)
    assert (response.status_code, response.json()["code"]) == (409, "text-not-available")
    assert "waiting to be processed" in response.json()["detail"]

    scan = upload(as_("lead"), "Scan.pdf", pdf_without_text())
    process(db, storage_root)
    failed = text(as_("lead"), scan).json()
    assert failed["detail"].startswith("Text extraction failed: This PDF has no text layer")

    image = upload(as_("lead"), "Photo.png", png_bytes(), "image/png")
    assert "OCR" in text(as_("lead"), image).json()["detail"]

    sample = str(sample_uuid("document", "d-18"))
    assert "no stored file" in text(as_("lead"), sample).json()["detail"]


def test_a_deleted_document_shows_no_text_to_anyone(as_: As, ready: str) -> None:
    assert as_("lead").delete(f"/api/documents/{ready}").status_code == 204
    for role in ("admin", "lead", "paralegal"):
        response = text(as_(role), ready)
        assert (response.status_code, response.json()["code"]) == (404, "document-not-found")
    as_("lead").post(f"/api/documents/{ready}/restore")
    assert text(as_("lead"), ready).status_code == 200  # kept, and back once restored


def test_text_stays_readable_on_an_archived_case(as_: As, ready: str) -> None:
    as_("admin").post(f"/api/cases/{SATTVIK}/archive")
    assert text(as_("lead"), ready).status_code == 200


# --- asking for a retry -----------------------------------------------------------------


def failed_scan(as_: As, db: Session, root: Path) -> str:
    document = upload(as_("lead"), "Scan.pdf", pdf_without_text())
    process(db, root)
    return document


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("admin", 200),
        ("lead", 200),
        ("associate", 200),
        ("paralegal", 200),
        ("other_advocate", 404),
    ],
)
def test_staff_who_may_upload_ask_for_a_retry(
    as_: As, db: Session, storage_root: Path, role: str, expected: int
) -> None:
    document = failed_scan(as_, db, storage_root)
    assert as_(role).post(f"/api/documents/{document}/reprocess").status_code == expected


def test_a_retry_queues_the_document_again_and_is_audited(
    as_: As, db: Session, storage_root: Path, people: dict[str, User]
) -> None:
    document = failed_scan(as_, db, storage_root)
    response = as_("paralegal").post(f"/api/documents/{document}/reprocess")
    processing = response.json()["processing"]
    assert (processing["status"], processing["reasonCode"]) == ("queued", None)
    job = db.get(DocumentExtraction, uuid.UUID(document), populate_existing=True)
    assert job is not None and (job.attempts, job.requested_by_id) == (0, people["paralegal"].id)
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "document.reprocessed")).one()
    assert event.details == {"previousStatus": "failed"}


def test_retries_that_cannot_help_are_refused(as_: As, storage_root: Path) -> None:
    waiting = upload(as_("lead"), "Waiting.pdf", pdf_with_pages(["FICTIONAL."]))
    queued = as_("lead").post(f"/api/documents/{waiting}/reprocess")
    assert (queued.status_code, queued.json()["code"]) == (409, "already-processing")
    image = upload(as_("lead"), "Photo.png", png_bytes(), "image/png")
    unsupported = as_("lead").post(f"/api/documents/{image}/reprocess")
    assert (unsupported.status_code, unsupported.json()["code"]) == (409, "unsupported")
    sample = sample_uuid("document", "d-18")
    no_file = as_("lead").post(f"/api/documents/{sample}/reprocess")
    assert (no_file.status_code, no_file.json()["code"]) == (422, "no-file")


def test_no_retry_on_an_archived_case_or_for_a_deleted_document(
    as_: As, db: Session, storage_root: Path
) -> None:
    document = failed_scan(as_, db, storage_root)
    other = failed_scan_named(as_, db, storage_root, "Other scan.pdf")
    as_("lead").delete(f"/api/documents/{other}")
    gone = as_("lead").post(f"/api/documents/{other}/reprocess")
    assert (gone.status_code, gone.json()["code"]) == (404, "document-not-found")
    as_("admin").post(f"/api/cases/{SATTVIK}/archive")
    archived = as_("admin").post(f"/api/documents/{document}/reprocess")
    assert (archived.status_code, archived.json()["code"]) == (409, "case-archived")


def failed_scan_named(as_: As, db: Session, root: Path, name: str) -> str:
    document = upload(as_("lead"), name, pdf_without_text())
    process(db, root)
    return document


def test_files_uploaded_before_extraction_existed_can_be_queued(as_: As, db: Session) -> None:
    document = upload(as_("lead"), "Older.pdf", pdf_with_pages(["FICTIONAL."]))
    job = db.get(DocumentExtraction, uuid.UUID(document))
    db.delete(job)  # as for a file stored before migration 0008
    db.flush()

    waiting = text(as_("lead"), document)
    assert (waiting.status_code, waiting.json()["code"]) == (409, "text-not-available")
    assert "uploaded before text extraction was available" in waiting.json()["detail"]
    assert "no stored file" not in waiting.json()["detail"]

    response = as_("lead").post(f"/api/documents/{document}/reprocess")
    assert response.status_code == 200, response.text
    assert response.json()["processing"]["status"] == "queued"
