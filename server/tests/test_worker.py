"""The document-processing worker, end to end (fixtures: access_fixtures).

Files are uploaded through the API, then the worker runs against the test
database and the test upload folder. Documents are fictional.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from lexflow import worker
from lexflow.config import Settings, get_settings
from lexflow.extraction import DOCX, Extracted, ExtractionError, Limits, extract
from lexflow.models import Document, DocumentChunk, DocumentExtraction, DocumentSection
from lexflow.services import extraction_queue as queue
from lexflow.storage import LocalDiskStorage
from tests.access_fixtures import SATTVIK
from tests.conftest import shared_sessions
from tests.document_fixtures import (
    SAMPLE_PAGES,
    docx_with,
    pdf_with_pages,
    pdf_without_text,
)

As = Callable[[str], TestClient]


def in_process(content_type: str, data: bytes, limits: Limits, timeout: float) -> Extracted:
    """The real extractors, without the child process (faster for most tests)."""
    return extract(content_type, data, limits)


def settings(**changes: Any) -> Settings:
    return get_settings().model_copy(update=changes)


def upload(http: TestClient, name: str, content: bytes, ctype: str) -> uuid.UUID:
    response = http.post(f"/api/cases/{SATTVIK}/documents", files={"file": (name, content, ctype)})
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


def run_once(
    db: Session, root: Path, *, config: Settings | None = None, extract_fn: Any = in_process
) -> int:
    return worker.run(
        shared_sessions(db),
        LocalDiskStorage(root),
        config or settings(),
        worker_id="test-worker",
        once=True,
        extract=extract_fn,
    )


def job(db: Session, document_id: uuid.UUID) -> DocumentExtraction:
    found = db.get(DocumentExtraction, document_id, populate_existing=True)
    assert found is not None
    return found


def test_a_multi_page_pdf_yields_page_numbered_text_and_chunks(
    as_: As, db: Session, storage_root: Path
) -> None:
    document = upload(as_("lead"), "Petition.pdf", pdf_with_pages(SAMPLE_PAGES), "application/pdf")
    assert run_once(db, storage_root) == 1

    done = job(db, document)
    assert (done.status, done.page_count, done.section_count) == ("ready", 3, 3)
    assert done.extractor and done.extractor.startswith("pypdf ")
    sections = db.scalars(
        select(DocumentSection)
        .where(DocumentSection.document_id == document)
        .order_by(DocumentSection.number)
    ).all()
    assert [(s.number, s.page_number, s.text) for s in sections] == [
        (i, i, text) for i, text in enumerate(SAMPLE_PAGES, start=1)
    ]
    chunks = queue.chunks_of(db, document)
    assert done.chunk_count == len(chunks) >= 3
    by_number = {s.number: s for s in sections}
    for chunk in chunks:
        section = by_number[chunk.section_number]
        assert chunk.page_number == section.page_number
        assert section.text[chunk.char_start : chunk.char_end] == chunk.text
    assert any("Annexure T-1" in c.text and c.page_number == 2 for c in chunks)

    listed = as_("lead").get(f"/api/cases/{SATTVIK}").json()["documents"]
    processing = next(d for d in listed if d["id"] == str(document))["processing"]
    assert processing | {"updatedAt": None} == {
        "status": "ready",
        "reasonCode": None,
        "reason": None,
        "pageCount": 3,
        "sectionCount": 3,
        "chunkCount": len(chunks),
        "indexStatus": "disabled",
        "updatedAt": None,
    }


def test_the_real_child_process_path_works(as_: As, db: Session, storage_root: Path) -> None:
    document = upload(as_("lead"), "Petition.pdf", pdf_with_pages(SAMPLE_PAGES), "application/pdf")
    assert run_once(db, storage_root, extract_fn=worker.default_extract) == 1
    assert job(db, document).status == "ready"


def test_a_word_document_has_parts_without_page_numbers(
    as_: As, db: Session, storage_root: Path
) -> None:
    document = upload(as_("lead"), "Notes.docx", docx_with(["FICTIONAL note one.", "Two."]), DOCX)
    run_once(db, storage_root)
    done = job(db, document)
    assert (done.status, done.page_count, done.section_count) == ("ready", None, 1)
    assert {c.page_number for c in queue.chunks_of(db, document)} == {None}


def test_a_scan_without_text_fails_with_a_visible_reason(
    as_: As, db: Session, storage_root: Path
) -> None:
    document = upload(as_("lead"), "Scan.pdf", pdf_without_text(2), "application/pdf")
    run_once(db, storage_root)
    failed = job(db, document)
    assert (failed.status, failed.reason_code) == ("failed", "no-text-layer")
    listed = as_("lead").get(f"/api/cases/{SATTVIK}").json()["documents"]
    shown = next(d for d in listed if d["id"] == str(document))["processing"]
    assert shown["status"] == "failed" and "no text layer" in shown["reason"]
    assert (
        db.scalars(select(DocumentSection).where(DocumentSection.document_id == document)).all()
        == []
    )


def test_a_changed_or_missing_file_is_not_processed(
    as_: As, db: Session, storage_root: Path
) -> None:
    changed = upload(
        as_("lead"), "Changed.pdf", pdf_with_pages(["FICTIONAL a."]), "application/pdf"
    )
    missing = upload(
        as_("lead"), "Missing.pdf", pdf_with_pages(["FICTIONAL b."]), "application/pdf"
    )
    store = LocalDiskStorage(storage_root)
    keys = {
        d.id: d.storage_key
        for d in db.scalars(select(Document).where(Document.id.in_([changed, missing])))
    }
    target = store._path(keys[changed] or "")
    target.write_bytes(pdf_with_pages(["FICTIONAL tampered."]))
    store.delete(keys[missing] or "")

    run_once(db, storage_root)
    assert (job(db, changed).status, job(db, changed).reason_code) == ("failed", "file-changed")
    assert (job(db, missing).status, job(db, missing).reason_code) == ("failed", "file-missing")


def test_unsupported_files_are_never_given_to_the_worker(
    as_: As, db: Session, storage_root: Path
) -> None:
    from tests.test_documents import png_bytes

    upload(as_("lead"), "Photo.png", png_bytes(), "image/png")
    assert run_once(db, storage_root) == 0


def test_a_crashing_extraction_is_retried_then_fails(
    as_: As, db: Session, storage_root: Path
) -> None:
    document = upload(as_("lead"), "Petition.pdf", pdf_with_pages(SAMPLE_PAGES), "application/pdf")
    calls: list[int] = []

    def crashes(content_type: str, data: bytes, limits: Limits, timeout: float) -> Extracted:
        calls.append(1)
        raise ExtractionError(
            "extractor-crashed", "The text extraction stopped unexpectedly.", retry=True
        )

    run_once(db, storage_root, extract_fn=crashes)
    assert len(calls) == get_settings().worker_max_attempts
    failed = job(db, document)
    assert (failed.status, failed.reason_code, failed.attempts) == (
        "failed",
        "extractor-crashed",
        get_settings().worker_max_attempts,
    )


def test_a_worker_whose_job_was_taken_over_stores_nothing(
    as_: As, db: Session, storage_root: Path
) -> None:
    document = upload(as_("lead"), "Petition.pdf", pdf_with_pages(SAMPLE_PAGES), "application/pdf")

    def slow_then_lost(content_type: str, data: bytes, limits: Limits, timeout: float) -> Extracted:
        # Meanwhile the lease expired and another worker took the job over.
        db.execute(
            update(DocumentExtraction)
            .where(DocumentExtraction.document_id == document)
            .values(worker_id="another-worker")
        )
        db.commit()
        return extract(content_type, data, limits)

    sessions = shared_sessions(db)
    with sessions() as session:
        claimed = queue.claim(
            session,
            worker_id="test-worker",
            now=datetime.now(UTC),
            lease_seconds=300,
            max_attempts=3,
        )
    assert claimed == document
    status = worker.process(
        sessions,
        LocalDiskStorage(storage_root),
        settings(),
        document,
        "test-worker",
        extract=slow_then_lost,
    )
    assert status == "discarded"
    assert job(db, document).worker_id == "another-worker"
    assert (
        db.scalars(select(DocumentSection).where(DocumentSection.document_id == document)).all()
        == []
    )


def test_an_interrupted_worker_hands_its_job_back(as_: As, db: Session, storage_root: Path) -> None:
    document = upload(as_("lead"), "Petition.pdf", pdf_with_pages(SAMPLE_PAGES), "application/pdf")

    def interrupted(content_type: str, data: bytes, limits: Limits, timeout: float) -> Extracted:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_once(db, storage_root, extract_fn=interrupted)
    back = job(db, document)
    assert (back.status, back.worker_id, back.lease_expires_at) == ("queued", None, None)
    assert run_once(db, storage_root) == 1  # the next run picks it up
    assert job(db, document).status == "ready"


def test_a_stale_job_from_a_dead_worker_is_recovered(
    as_: As, db: Session, storage_root: Path
) -> None:
    document = upload(as_("lead"), "Petition.pdf", pdf_with_pages(SAMPLE_PAGES), "application/pdf")
    sessions = shared_sessions(db)
    long_ago = datetime.now(UTC) - timedelta(hours=1)
    with sessions() as session:
        assert (
            queue.claim(session, worker_id="dead", now=long_ago, lease_seconds=300, max_attempts=3)
            == document
        )
    assert run_once(db, storage_root) == 1
    recovered = job(db, document)
    assert (recovered.status, recovered.attempts) == ("ready", 2)


def test_processing_again_gives_the_same_chunks(as_: As, db: Session, storage_root: Path) -> None:
    document = upload(as_("lead"), "Petition.pdf", pdf_with_pages(SAMPLE_PAGES), "application/pdf")
    run_once(db, storage_root)
    first = [
        (c.number, c.char_start, c.char_end, c.content_sha256)
        for c in queue.chunks_of(db, document)
    ]
    row = db.get(Document, document)
    assert row is not None
    queue.queue(db, row, requested_by=None, now=datetime.now(UTC))
    db.commit()
    run_once(db, storage_root)
    again = [
        (c.number, c.char_start, c.char_end, c.content_sha256)
        for c in queue.chunks_of(db, document)
    ]
    assert again == first
    assert db.scalar(select(DocumentChunk.id).where(DocumentChunk.document_id == document).limit(1))


def test_the_worker_refuses_a_missing_database(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from sqlalchemy.exc import OperationalError

    def broken(*_: object, **__: object) -> int:
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(worker, "run", broken)
    assert worker.main(["--once"]) == 1
    assert "alembic upgrade head" in capsys.readouterr().err
