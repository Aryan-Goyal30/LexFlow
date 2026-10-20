"""The document-processing queue (fixtures: access_fixtures).

Uploading queues a job; ``claim`` hands jobs to workers under a lease;
``complete`` stores the outcome only for the worker that still holds the job.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from lexflow.extraction import Section
from lexflow.models import Document, DocumentChunk, DocumentExtraction, DocumentSection
from lexflow.seed import sample_uuid
from lexflow.seed.loader import load_sample_data
from lexflow.services import documents as documents_service
from lexflow.services import extraction_queue as queue
from lexflow.services.extraction_queue import ChunkData, Failure, Success
from lexflow.storage import LocalDiskStorage
from tests.access_fixtures import SATTVIK
from tests.test_documents import PDF, docx_bytes, png_bytes

As = Callable[[str], TestClient]
NOW = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
LEASE, MAX = 300, 3
DOC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 504  # legacy Word header


def upload(http: TestClient, name: str, content: bytes, ctype: str) -> dict[str, Any]:
    response = http.post(f"/api/cases/{SATTVIK}/documents", files={"file": (name, content, ctype)})
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def claim(db: Session, worker: str = "w1", now: datetime = NOW) -> uuid.UUID | None:
    return queue.claim(db, worker_id=worker, now=now, lease_seconds=LEASE, max_attempts=MAX)


def job(db: Session, document_id: str | uuid.UUID) -> DocumentExtraction:
    found = db.get(DocumentExtraction, uuid.UUID(str(document_id)), populate_existing=True)
    assert found is not None
    return found


def success(document_id: uuid.UUID, pages: list[str]) -> Success:
    sections = [Section(page_number=i, text=t) for i, t in enumerate(pages, start=1)]
    chunks = [
        ChunkData(
            number=i,
            section_number=i,
            page_number=i,
            char_start=0,
            char_end=len(t),
            text=t,
            content_sha256="0" * 64,
        )
        for i, t in enumerate(pages, start=1)
    ]
    return Success(sections=sections, chunks=chunks, extractor="test extractor", page_count=2)


# --- queueing on upload ---------------------------------------------------------------


def test_an_uploaded_pdf_word_or_text_file_is_queued(as_: As, storage_root: Any) -> None:
    for name, content, ctype in (
        ("Brief.pdf", PDF, "application/pdf"),
        (
            "Notes.docx",
            docx_bytes(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        ("Memo.txt", b"Hello", "text/plain"),
    ):
        processing = upload(as_("lead"), name, content, ctype)["processing"]
        assert processing["status"] == "queued", name
        assert processing["reasonCode"] is None and processing["indexStatus"] == "disabled"
        assert processing["sectionCount"] is None and processing["chunkCount"] is None


def test_images_and_old_word_files_are_unsupported_with_a_reason(
    as_: As, storage_root: Any
) -> None:
    image = upload(as_("lead"), "Photo.png", png_bytes(), "image/png")["processing"]
    assert (image["status"], image["reasonCode"]) == ("unsupported", "unsupported-type")
    assert image["reason"] == "Text is not extracted from images (OCR is not available)."
    old = upload(as_("lead"), "Old.doc", DOC, "application/msword")["processing"]
    assert old["status"] == "unsupported"
    assert ".docx" in old["reason"]


def test_records_without_a_file_have_no_processing(as_: As) -> None:
    detail = as_("lead").get(f"/api/cases/{SATTVIK}").json()
    samples = [d for d in detail["documents"] if not d["hasFile"]]
    assert samples and all(d["processing"] is None for d in samples)


def test_the_case_detail_shows_each_documents_status(as_: As, storage_root: Any) -> None:
    created = upload(as_("lead"), "Brief.pdf", PDF, "application/pdf")
    detail = as_("paralegal").get(f"/api/cases/{SATTVIK}").json()
    listed = next(d for d in detail["documents"] if d["id"] == created["id"])
    assert listed["processing"]["status"] == "queued"


# --- claiming -----------------------------------------------------------------------------


def test_workers_get_the_oldest_waiting_job_with_a_lease(
    as_: As, db: Session, storage_root: Any
) -> None:
    first = upload(as_("lead"), "One.pdf", PDF, "application/pdf")["id"]
    second = upload(as_("lead"), "Two.txt", b"two", "text/plain")["id"]
    # Both times explicit: the upload stamps the real clock, which says nothing
    # about NOW (a fixed date).
    job(db, first).queued_at = NOW
    job(db, second).queued_at = NOW + timedelta(seconds=1)
    db.commit()

    assert str(claim(db, "w1")) == first
    held = job(db, first)
    assert (held.status, held.attempts, held.worker_id) == ("processing", 1, "w1")
    assert held.lease_expires_at == NOW + timedelta(seconds=LEASE)
    assert str(claim(db, "w2")) == second
    assert claim(db, "w3") is None  # nothing else is waiting


def test_an_expired_lease_is_taken_over_and_the_old_worker_is_ignored(
    as_: As, db: Session, storage_root: Any
) -> None:
    document = uuid.UUID(upload(as_("lead"), "One.pdf", PDF, "application/pdf")["id"])
    assert claim(db, "dead") == document
    assert claim(db, "w2", NOW + timedelta(seconds=LEASE - 1)) is None  # still leased
    later = NOW + timedelta(seconds=LEASE + 1)
    assert claim(db, "w2", later) == document
    assert job(db, document).attempts == 2

    stale = queue.complete(
        db,
        document,
        worker_id="dead",
        outcome=success(document, ["x"]),
        now=later,
        max_attempts=MAX,
    )
    assert stale == "discarded"
    assert job(db, document).status == "processing"
    assert db.scalar(select(func.count()).select_from(DocumentSection)) == 0

    done = queue.complete(
        db,
        document,
        worker_id="w2",
        outcome=success(document, ["page one", "page two"]),
        now=later,
        max_attempts=MAX,
    )
    assert done == "ready"


def test_a_job_abandoned_on_its_last_attempt_fails_instead_of_looping(
    as_: As, db: Session, storage_root: Any
) -> None:
    document = uuid.UUID(upload(as_("lead"), "One.pdf", PDF, "application/pdf")["id"])
    moment = NOW
    for _ in range(MAX):
        assert claim(db, "crashing", moment) == document
        moment += timedelta(seconds=LEASE + 1)
    assert claim(db, "next", moment) is None
    failed = job(db, document)
    assert (failed.status, failed.reason_code) == ("failed", "interrupted")
    assert failed.reason == queue.INTERRUPTED
    assert failed.lease_expires_at is None and failed.worker_id is None


# --- outcomes -----------------------------------------------------------------------------


def test_a_temporary_failure_is_retried_then_fails_with_its_reason(
    as_: As, db: Session, storage_root: Any
) -> None:
    document = uuid.UUID(upload(as_("lead"), "One.pdf", PDF, "application/pdf")["id"])
    trouble = Failure("storage-unavailable", "The stored file could not be read.", retry=True)
    statuses = []
    for _ in range(MAX):
        assert claim(db) == document
        statuses.append(
            queue.complete(db, document, worker_id="w1", outcome=trouble, now=NOW, max_attempts=MAX)
        )
    assert statuses == ["queued", "queued", "failed"]
    failed = job(db, document)
    assert (failed.reason_code, failed.reason) == (trouble.code, trouble.message)


def test_a_permanent_failure_is_not_retried(as_: As, db: Session, storage_root: Any) -> None:
    document = uuid.UUID(upload(as_("lead"), "One.pdf", PDF, "application/pdf")["id"])
    assert claim(db) == document
    outcome = Failure("no-text-layer", "This PDF has no text layer.")
    assert (
        queue.complete(db, document, worker_id="w1", outcome=outcome, now=NOW, max_attempts=MAX)
        == "failed"
    )
    assert claim(db) is None


def test_success_stores_sections_and_chunks_and_a_rerun_replaces_them(
    as_: As, db: Session, storage_root: Any
) -> None:
    document = uuid.UUID(upload(as_("lead"), "One.pdf", PDF, "application/pdf")["id"])
    assert claim(db) == document
    queue.complete(
        db,
        document,
        worker_id="w1",
        outcome=success(document, ["one", "two"]),
        now=NOW,
        max_attempts=MAX,
        index_status="pending",
    )
    ready = job(db, document)
    assert (ready.status, ready.section_count, ready.chunk_count, ready.char_count) == (
        "ready",
        2,
        2,
        6,
    )
    assert (ready.extractor, ready.page_count, ready.index_status) == (
        "test extractor",
        2,
        "pending",
    )

    # Re-queued (for example after an extractor upgrade) and processed again.
    document_row = db.get(Document, document)
    assert document_row is not None
    queue.queue(db, document_row, requested_by=None, now=NOW)
    db.commit()
    requeued = job(db, document)
    assert (requeued.status, requeued.attempts, requeued.section_count) == ("queued", 0, None)
    assert claim(db) == document
    queue.complete(
        db,
        document,
        worker_id="w1",
        outcome=success(document, ["only page"]),
        now=NOW,
        max_attempts=MAX,
    )
    texts = db.scalars(
        select(DocumentSection.text).where(DocumentSection.document_id == document)
    ).all()
    assert texts == ["only page"]
    assert [c.text for c in queue.chunks_of(db, document)] == ["only page"]


def test_purging_a_document_removes_its_text(as_: As, db: Session, storage_root: Any) -> None:
    document = uuid.UUID(upload(as_("lead"), "One.pdf", PDF, "application/pdf")["id"])
    assert claim(db) == document
    queue.complete(
        db, document, worker_id="w1", outcome=success(document, ["one"]), now=NOW, max_attempts=MAX
    )
    as_("lead").delete(f"/api/documents/{document}")
    assert documents_service.purge(db, LocalDiskStorage(storage_root), document) is True
    for model in (DocumentExtraction, DocumentSection, DocumentChunk):
        assert db.scalar(select(func.count()).select_from(model)) == 0, model.__name__


def test_a_failed_job_without_a_reason_is_impossible(
    as_: As, db: Session, storage_root: Any
) -> None:
    document = upload(as_("lead"), "One.pdf", PDF, "application/pdf")["id"]
    with pytest.raises(IntegrityError):
        db.execute(
            text("UPDATE document_extractions SET status = 'failed' WHERE document_id = :d"),
            {"d": document},
        )
        db.flush()


# --- concurrency (real connections) ------------------------------------------------------


def test_concurrent_workers_never_take_the_same_job(committed_engine: Engine) -> None:
    with Session(committed_engine) as session, session.begin():
        load_sample_data(session)
        documents = [
            Document(
                case_id=sample_uuid("case", "case-1005"),
                name=f"Concurrent {i}.txt",
                document_type="Text",
                content_type="text/plain",
                size_bytes=1,
                sha256="0" * 64,
                storage_key=uuid.uuid4().hex,
                uploaded_on=date(2026, 10, 20),
            )
            for i in range(6)
        ]
        session.add_all(documents)
        session.flush()
        for document in documents:
            queue.queue(session, document, requested_by=None, now=NOW)
        expected = sorted(d.id for d in documents)

    claimed: list[uuid.UUID] = []
    lock = threading.Lock()

    def work(name: str) -> None:
        with Session(committed_engine) as session:
            while (got := claim(session, name)) is not None:
                with lock:
                    claimed.append(got)

    threads = [threading.Thread(target=work, args=(f"w{i}",)) for i in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert sorted(claimed) == expected  # each exactly once


def test_a_job_locked_by_one_worker_is_skipped_by_another(committed_engine: Engine) -> None:
    with Session(committed_engine) as session, session.begin():
        load_sample_data(session)
        documents = [
            Document(
                case_id=sample_uuid("case", "case-1005"),
                name=f"Locked {i}.txt",
                document_type="Text",
                content_type="text/plain",
                size_bytes=1,
                sha256="0" * 64,
                storage_key=uuid.uuid4().hex,
                uploaded_on=date(2026, 10, 20),
            )
            for i in range(2)
        ]
        session.add_all(documents)
        session.flush()
        for offset, document in enumerate(documents):
            queue.queue(session, document, requested_by=None, now=NOW + timedelta(seconds=offset))
        oldest, newer = documents[0].id, documents[1].id

    with Session(committed_engine) as holder:
        holder.execute(
            select(DocumentExtraction)
            .where(DocumentExtraction.document_id == oldest)
            .with_for_update()
        )
        with Session(committed_engine) as other:
            assert claim(other, "w2") == newer  # did not wait for the lock
        holder.rollback()
