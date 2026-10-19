"""Uploading, reading and deleting case documents.

Consistency between the database and the file store:

- Upload: stream to a staging file (hash, size limit, content check), insert
  the row and flush (duplicate names fail here, before any file moves), move the
  file into place, commit. If the commit fails the stored file is removed; the
  staging file is always removed.
- Delete: commit the row removal first, then delete the file. A failure can at
  worst leave an orphaned file, never a record pointing at a missing file.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import date

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from lexflow.errors import ProblemError
from lexflow.models import Document
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
            Document.case_id == case_id, func.lower(Document.name) == name.lower()
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
        )
        session.add(document)
        try:
            session.flush()
        except IntegrityError:
            # A concurrent upload took the same name between the check and here.
            session.rollback()
            raise _duplicate(name) from None

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


def delete_document(session: Session, storage: Storage, document_id: uuid.UUID) -> None:
    """Remove the record, then its file (if it has one). Commits."""
    document = get_document(session, document_id)
    key = document.storage_key
    session.delete(document)
    session.commit()
    if key is not None:
        try:
            storage.delete(key)
        except OSError:
            # The record is gone; an orphaned file is harmless and can be cleaned up.
            logger.warning("Could not delete stored file for document %s", document_id)
