"""Reading a document's extracted text, and asking for it to be extracted again.

Who may do what follows the document's case (``lexflow.authz``): staff on the
case read the text; staff who may upload to it ask for a retry. Deleted
documents and documents on cases a user may not see are not found. Client
accounts never reach these routes (they are staff routes).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lexflow.errors import ProblemError
from lexflow.models import Document, DocumentChunk, DocumentExtraction, DocumentSection
from lexflow.schemas import DocumentTextOut, DocumentTextSectionOut

NOT_READY = {
    "queued": "The text has not been extracted yet. It is waiting to be processed.",
    "processing": "The text is being extracted. Try again in a moment.",
}


def not_available(job: DocumentExtraction | None) -> ProblemError:
    if job is None:
        message = "This record has no stored file, so it has no text."
    elif job.status in NOT_READY:
        message = NOT_READY[job.status]
    elif job.status == "failed":
        message = f"Text extraction failed: {job.reason}"
    else:  # unsupported
        message = job.reason or "Text is not extracted from this type of file."
    return ProblemError(409, "text-not-available", message)


def read_section(session: Session, document: Document, number: int) -> DocumentTextOut:
    job = session.get(DocumentExtraction, document.id)
    if job is None or job.status != "ready":
        raise not_available(job)
    section = session.get(DocumentSection, (document.id, number))
    if section is None:
        raise ProblemError(
            404,
            "section-not-found",
            f"This document has {job.section_count} "
            f"{'page' if job.page_count is not None else 'part'}"
            f"{'' if job.section_count == 1 else 's'}.",
        )
    chunks = session.scalar(
        select(func.count())
        .select_from(DocumentChunk)
        .where(DocumentChunk.document_id == document.id, DocumentChunk.section_number == number)
    )
    return DocumentTextOut.model_validate(
        {
            "document_id": document.id,
            "document_name": document.name,
            "extractor": job.extractor,
            "page_count": job.page_count,
            "section_count": job.section_count,
            "char_count": job.char_count,
            "extracted_at": job.finished_at,
            "section": DocumentTextSectionOut(
                number=section.number,
                page_number=section.page_number,
                text=section.text,
                chunk_count=chunks or 0,
            ),
        }
    )


def can_reprocess(job: DocumentExtraction | None) -> None:
    """Refuse a retry that cannot help (or is already happening)."""
    if job is None:
        raise ProblemError(422, "no-file", "This record has no stored file, so it has no text.")
    if job.status in ("queued", "processing"):
        raise ProblemError(
            409, "already-processing", "The text is already waiting to be extracted."
        )
    if job.status == "unsupported":
        raise ProblemError(
            409, "unsupported", job.reason or "Text is not extracted from this type of file."
        )
