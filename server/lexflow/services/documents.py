"""Uploading, reading, deleting, restoring and purging case documents.

Consistency between the database and the file store:

- Upload: stream to a staging file (hash, size limit, content check), insert
  the row and flush (duplicate names fail here, before any file moves), move the
  file into place, commit. If the commit fails the stored file is removed; the
  staging file is always removed.
- Delete (in the app) is soft: the row is marked deleted and the file is kept,
  so the document can be restored.
- Purge (only ``python -m lexflow.cli.documents purge``): commit the row removal
  first, then delete the file. A failure can at worst leave an orphaned file,
  never a record pointing at a missing file.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from lexflow.errors import ProblemError
from lexflow.models import Document
from lexflow.services import extraction_queue
from lexflow.services.cases import get_case
from lexflow.services.formatting import format_file_size
from lexflow.services.uploads import (
    ACCEPTED_LABEL,
    HEAD_BYTES,
    TextCheck,
    clean_filename,
    content_matches,
    kind_for,
)
from lexflow.storage import Storage

CHUNK = 1024 * 1024
logger = logging.getLogger("lexflow.documents")

DOCUMENT_NOT_FOUND = "No document with this id exists."


def _duplicate(name: str) -> ProblemError:
    return ProblemError(409, "duplicate", f"{name} is already attached to this case.")


def too_large(limit: int) -> ProblemError:
    return ProblemError(
        413,
        "too-large",
        f"This file is larger than the {format_file_size(limit)} upload limit.",
    )


def parse_document_id(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise ProblemError(404, "document-not-found", DOCUMENT_NOT_FOUND) from None


def get_document(session: Session, document_id: uuid.UUID) -> Document:
    document = session.get(Document, document_id)
    if document is None:
        raise ProblemError(404, "document-not-found", DOCUMENT_NOT_FOUND)
    return document


def upload_document(
    session: Session,
    storage: Storage,
    case_id: uuid.UUID,
    upload: UploadFile,
    max_bytes: int,
    today: date,
    uploaded_by: uuid.UUID | None = None,
    now: datetime | None = None,
) -> uuid.UUID:
    """Validate and store one uploaded file on a case. Commits. Returns the document id.

    Synchronous (database, disk, hashing), so the route runs it in the thread pool.
    By then FastAPI has already received the form; the size limit middleware has
    cut off oversized bodies while they were streaming in.
    """
    get_case(session, case_id)  # 404 if the case doesn't exist

    name = clean_filename(upload.filename)
    if not name:
        raise ProblemError(422, "invalid-name", "The file has no usable name.")
    kind = kind_for(name)
    if kind is None:
        raise ProblemError(
            415, "unsupported-type", f"{name} is not a supported file type. Use {ACCEPTED_LABEL}."
        )
    if session.scalar(
        select(Document.id).where(
            Document.case_id == case_id,
            func.lower(Document.name) == name.lower(),
            Document.deleted_at.is_(None),
        )
    ):
        raise _duplicate(name)

    with storage.staging_file() as (staged_path, staged):
        hasher = hashlib.sha256()
        text = TextCheck()
        head = b""
        size = 0
        while chunk := upload.file.read(CHUNK):
            size += len(chunk)
            if size > max_bytes:
                raise too_large(max_bytes)
            if len(head) < HEAD_BYTES:
                head += chunk[: HEAD_BYTES - len(head)]
            hasher.update(chunk)
            text.feed(chunk)
            staged.write(chunk)
        text.feed(b"", final=True)
        staged.close()

        if size == 0:
            raise ProblemError(422, "empty", f"{name} is empty.")
        # The same file under another name would put the same evidence in the
        # case twice (analysis would count it twice); other cases may hold it.
        same = session.scalar(
            select(Document.name).where(
                Document.case_id == case_id,
                Document.sha256 == hasher.hexdigest(),
                Document.deleted_at.is_(None),
            )
        )
        if same is not None:
            raise ProblemError(
                409,
                "duplicate-content",
                f"{name} has the same content as {same}, which is already attached to this case.",
            )
        if not content_matches(kind, head, staged_path, text.ok):
            raise ProblemError(
                415,
                "content-mismatch",
                f"The contents of {name} don't match its file type.",
            )

        key = storage.new_key()
        document = Document(
            case_id=case_id,
            name=name,
            document_type=kind.label,
            content_type=kind.content_type,
            size_bytes=size,
            sha256=hasher.hexdigest(),
            storage_key=key,
            uploaded_on=today,
            uploaded_by_id=uploaded_by,
        )
        session.add(document)
        try:
            session.flush()
        except IntegrityError:
            # A concurrent upload took the same name between the check and here.
            session.rollback()
            raise _duplicate(name) from None
        # Its text is extracted in the background (or it is marked unsupported),
        # in the same transaction: a stored file always has a job.
        extraction_queue.queue(
            session, document, requested_by=uploaded_by, now=now or datetime.now(UTC)
        )
        session.flush()

        try:
            storage.put(key, staged_path)
        except Exception:
            session.rollback()  # the flushed row must not outlive a failed store
            raise
        try:
            session.commit()
        except Exception:
            session.rollback()
            storage.delete(key)
            raise
    return document.id


def soft_delete(session: Session, document: Document, *, by: uuid.UUID, now: datetime) -> None:
    """Hide a document from the case, keeping its row and file. Commits.

    It also stops being shared with the client; restoring does not share it again.
    """
    document.deleted_at, document.deleted_by_id = now, by
    document.shared_with_client_at, document.shared_by_id = None, None
    session.commit()


def set_shared(
    session: Session, document: Document, *, share: bool, by: uuid.UUID, now: datetime
) -> bool:
    """Share a document with the case's client, or stop. Commits. False if unchanged.

    Only stored files can be shared (sample records have none).
    """
    if (document.shared_with_client_at is not None) == share:
        return False
    if share and document.storage_key is None:
        raise ProblemError(
            422, "no-file", "This is a sample record with no stored file; it cannot be shared."
        )
    document.shared_with_client_at, document.shared_by_id = (now, by) if share else (None, None)
    session.commit()
    return True


def restore(session: Session, document: Document) -> bool:
    """Bring a deleted document back. Commits. False if it was not deleted.

    Refused (409 ``duplicate``) while a live document on the case has the same
    name, and (409 ``duplicate-content``) while one has the same content: one of
    them must be renamed or deleted first.
    """
    if document.deleted_at is None:
        return False
    clash = session.scalar(
        select(Document.id).where(
            Document.case_id == document.case_id,
            func.lower(Document.name) == document.name.lower(),
            Document.deleted_at.is_(None),
        )
    )
    if clash is not None:
        raise _name_taken(document.name)
    if document.sha256 is not None:
        same = session.scalar(
            select(Document.name).where(
                Document.case_id == document.case_id,
                Document.sha256 == document.sha256,
                Document.deleted_at.is_(None),
            )
        )
        if same is not None:
            raise ProblemError(
                409,
                "duplicate-content",
                f"{same} on this case has the same content as {document.name}. "
                "Delete it, then restore.",
            )
    document.deleted_at, document.deleted_by_id = None, None
    try:
        session.commit()
    except IntegrityError:
        # A document with this name was uploaded between the check and the commit.
        session.rollback()
        raise _name_taken(document.name) from None
    return True


def _name_taken(name: str) -> ProblemError:
    return ProblemError(
        409,
        "duplicate",
        f"Another document named {name} is on this case. Delete or rename it, then restore.",
    )


def deleted_documents(session: Session, case_id: uuid.UUID) -> list[Document]:
    """A case's deleted documents, most recently deleted first."""
    return list(
        session.scalars(
            select(Document)
            .where(Document.case_id == case_id, Document.deleted_at.is_not(None))
            .order_by(Document.deleted_at.desc(), Document.id)
        )
    )


def purge(session: Session, storage: Storage, document_id: uuid.UUID) -> bool:
    """Permanently remove a deleted document: the record, then its file. Commits.

    Only for the operator command. Locks the row and checks it is still deleted
    (someone may have restored it since the preview); returns False if not.
    """
    document = session.get(Document, document_id, with_for_update=True)
    if document is None or document.deleted_at is None:
        session.rollback()
        return False
    key = document.storage_key
    session.delete(document)
    session.commit()
    if key is not None:
        try:
            storage.delete(key)
        except OSError:
            # The record is gone; an orphaned file is harmless and can be cleaned up.
            logger.warning("Could not delete stored file for document %s", document_id)
    return True
