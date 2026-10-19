"""The document-processing queue (Phase 3), kept in ``document_extractions``.

- ``queue`` creates or resets a document's job: ``queued`` for PDF, Word
  (.docx) and text files, ``unsupported`` (with the reason) for anything else.
- ``claim`` gives a worker the oldest waiting job. It takes the row with
  ``FOR UPDATE SKIP LOCKED``, so two workers never get the same job, and
  reserves it with a lease: if the worker dies, another worker takes the job
  over once the lease has expired. A job that has already been tried
  ``max_attempts`` times is failed instead of being tried again.
- ``complete`` stores the outcome. It only does so for the worker that still
  holds the job; a worker whose lease was taken over (or whose job was
  re-queued meanwhile) has its result discarded.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.orm import Session

from lexflow.extraction import EXTRACTABLE_TYPES, Section, unsupported_reason
from lexflow.models import Document, DocumentChunk, DocumentExtraction, DocumentSection

logger = logging.getLogger("lexflow.extraction")

INTERRUPTED = "Processing stopped unexpectedly too many times. Try again later."


@dataclass(frozen=True)
class ChunkData:
    number: int
    section_number: int
    page_number: int | None
    char_start: int
    char_end: int
    text: str
    content_sha256: str


@dataclass(frozen=True)
class Success:
    sections: list[Section]
    chunks: list[ChunkData]
    extractor: str
    page_count: int | None


@dataclass(frozen=True)
class Failure:
    code: str
    message: str
    retry: bool = False


def _reset(job: DocumentExtraction) -> None:
    job.attempts = 0
    job.started_at = job.finished_at = job.lease_expires_at = None
    job.worker_id = None
    job.extractor = None
    job.page_count = job.section_count = job.char_count = job.chunk_count = None
    job.index_status, job.index_reason = "disabled", None
    job.embedding_model = job.indexed_at = None


def queue(
    session: Session,
    document: Document,
    *,
    requested_by: uuid.UUID | None,
    now: datetime,
) -> DocumentExtraction:
    """Create or reset the job of a stored document. The caller commits.

    Text extracted earlier stays until a new result replaces it; it is not shown
    while the job is not ``ready``.
    """
    job = session.get(DocumentExtraction, document.id, with_for_update=True)
    if job is None:
        job = DocumentExtraction(document_id=document.id)
        session.add(job)
    _reset(job)
    job.queued_at = now
    job.requested_by_id = requested_by
    if document.content_type in EXTRACTABLE_TYPES:
        job.status, job.reason_code, job.reason = "queued", None, None
    else:
        job.status, job.reason_code = "unsupported", "unsupported-type"
        job.reason = unsupported_reason(document.content_type)
    return job


def claim(
    session: Session,
    *,
    worker_id: str,
    now: datetime,
    lease_seconds: int,
    max_attempts: int,
) -> uuid.UUID | None:
    """Take the oldest waiting job (or one whose worker's lease expired). Commits."""
    # Jobs abandoned after their last allowed attempt are failed, not retried.
    abandoned = (
        session.execute(
            update(DocumentExtraction)
            .where(
                DocumentExtraction.status == "processing",
                DocumentExtraction.lease_expires_at < now,
                DocumentExtraction.attempts >= max_attempts,
            )
            .values(
                status="failed",
                reason_code="interrupted",
                reason=INTERRUPTED,
                lease_expires_at=None,
                worker_id=None,
                finished_at=now,
            )
            .returning(DocumentExtraction.document_id)
        )
        .scalars()
        .all()
    )
    for document_id in abandoned:
        logger.warning("document %s: abandoned after %d attempts", document_id, max_attempts)

    candidate = (
        select(DocumentExtraction.document_id)
        .where(
            or_(
                DocumentExtraction.status == "queued",
                and_(
                    DocumentExtraction.status == "processing",
                    DocumentExtraction.lease_expires_at < now,
                ),
            )
        )
        .order_by(DocumentExtraction.queued_at, DocumentExtraction.document_id)
        .limit(1)
        .with_for_update(skip_locked=True)
        .scalar_subquery()
    )
    claimed = session.execute(
        update(DocumentExtraction)
        .where(DocumentExtraction.document_id == candidate)
        .values(
            status="processing",
            attempts=DocumentExtraction.attempts + 1,
            started_at=now,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
            worker_id=worker_id,
        )
        .returning(DocumentExtraction.document_id)
    ).scalar_one_or_none()
    session.commit()
    return claimed


def complete(
    session: Session,
    document_id: uuid.UUID,
    *,
    worker_id: str,
    outcome: Success | Failure,
    now: datetime,
    max_attempts: int,
    index_status: str = "disabled",
) -> str:
    """Store a job's outcome. Commits. Returns the job's new status, or
    ``"discarded"`` when this worker no longer holds the job."""
    job = session.get(DocumentExtraction, document_id, with_for_update=True, populate_existing=True)
    if job is None or job.status != "processing" or job.worker_id != worker_id:
        session.rollback()
        logger.warning("document %s: result discarded (the job is no longer ours)", document_id)
        return "discarded"

    if isinstance(outcome, Failure):
        if outcome.retry and job.attempts < max_attempts:
            job.status, job.reason_code, job.reason = "queued", None, None
        else:
            job.status, job.reason_code, job.reason = "failed", outcome.code, outcome.message
            job.finished_at = now
        job.lease_expires_at, job.worker_id = None, None
        session.commit()
        return job.status

    # Replace any earlier text in the same transaction (chunks cascade). The
    # job row changes only after this, all at once, so no flush ever sees a
    # half-updated job (the database checks status and lease together).
    session.execute(delete(DocumentSection).where(DocumentSection.document_id == document_id))
    session.add_all(
        DocumentSection(
            document_id=document_id, number=number, page_number=s.page_number, text=s.text
        )
        for number, s in enumerate(outcome.sections, start=1)
    )
    session.flush()
    session.add_all(
        DocumentChunk(
            document_id=document_id,
            number=c.number,
            section_number=c.section_number,
            page_number=c.page_number,
            char_start=c.char_start,
            char_end=c.char_end,
            text=c.text,
            content_sha256=c.content_sha256,
        )
        for c in outcome.chunks
    )
    session.flush()
    job.status, job.reason_code, job.reason = "ready", None, None
    job.lease_expires_at, job.worker_id = None, None
    job.finished_at = now
    job.extractor = outcome.extractor
    job.page_count = outcome.page_count
    job.section_count = len(outcome.sections)
    job.char_count = sum(len(s.text) for s in outcome.sections)
    job.chunk_count = len(outcome.chunks)
    job.index_status = index_status
    session.commit()
    return "ready"


def chunks_of(session: Session, document_id: uuid.UUID) -> list[DocumentChunk]:
    return list(
        session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.number)
        )
    )
