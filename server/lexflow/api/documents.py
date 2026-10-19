"""Uploading, listing, downloading, deleting and restoring case documents (staff).

Every route resolves the document's case through ``lexflow.authz``: a document
on a case the user may not see answers 404 like one that does not exist. A
deleted document answers 404 everywhere except the restore routes.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import date, datetime
from typing import BinaryIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile as StarletteUploadFile

from lexflow import authz
from lexflow.audit import AuditLog, get_audit_log
from lexflow.auth.deps import require_user
from lexflow.authz import Action
from lexflow.clock import get_now, get_today
from lexflow.db import get_session
from lexflow.errors import FieldError, ProblemError, problem_responses
from lexflow.models import Document, DocumentExtraction, User
from lexflow.schemas import DeletedDocumentOut, DocumentOut
from lexflow.services import cases as case_service
from lexflow.services import documents as service
from lexflow.services.uploads import KINDS
from lexflow.storage import Storage, get_storage

router = APIRouter(tags=["documents"])

READ_CHUNK = 64 * 1024
# Inline images and text are rendered in a sandbox with nothing else allowed.
SANDBOX_CSP = "sandbox; default-src 'none'; img-src 'self'; style-src 'unsafe-inline'"


def get_upload_limit(request: Request) -> int:
    limit: int = request.app.state.upload_limit
    return limit


@router.get(
    "/cases/{case_id}/documents",
    response_model=list[DocumentOut],
    responses=problem_responses(404),
)
def list_documents(
    case_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    today: date = Depends(get_today),
) -> list[DocumentOut]:
    """The documents on a case, newest first."""
    case, rel = authz.load_case(
        session, user, case_service.parse_case_id(case_id), Action.VIEW, audit
    )
    return case_service.get_case_detail(session, case.id, today, rel).documents


# The multipart body is described here because the route reads it itself.
UPLOAD_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["file"],
                    "properties": {
                        "file": {
                            "type": "string",
                            "format": "binary",
                            "description": "One file: PDF, Word, text, PNG, JPG, GIF or WebP.",
                        }
                    },
                }
            }
        },
    }
}


@router.post(
    "/cases/{case_id}/documents",
    response_model=DocumentOut,
    status_code=201,
    responses=problem_responses(404, 409, 413, 415, 422),
    openapi_extra=UPLOAD_BODY,
)
async def upload_document(
    case_id: str,
    request: Request,
    response: Response,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    storage: Storage = Depends(get_storage),
    audit: AuditLog = Depends(get_audit_log),
    limit: int = Depends(get_upload_limit),
    today: date = Depends(get_today),
    now: datetime = Depends(get_now),
) -> DocumentOut:
    """Attach one file to a case.

    The file's real content must match its extension. Errors carry a ``code``:
    ``unsupported-type``, ``content-mismatch``, ``empty``, ``duplicate``,
    ``too-large`` or ``invalid-name``.
    """
    # Who may upload here is settled before the body is read: the dependencies
    # above identified the user (a declared File() parameter would be read
    # before them), and the case is checked now.
    case, _ = await run_in_threadpool(
        authz.load_case,
        session,
        user,
        case_service.parse_case_id(case_id),
        Action.UPLOAD_DOCUMENT,
        audit,
    )
    async with request.form(max_files=1, max_fields=1) as form:
        upload = form.get("file")
        if not isinstance(upload, StarletteUploadFile):
            raise ProblemError(
                422,
                "validation-error",
                "Correct the highlighted fields and try again.",
                title="Some fields are invalid",
                errors=[FieldError(field="file", message="Field required")],
            )
        # Database, disk and hashing work runs in the thread pool, so it never
        # blocks the event loop (and other requests) while it runs.
        document_id = await run_in_threadpool(
            service.upload_document,
            session,
            storage,
            case.id,
            upload,
            limit,
            today,
            user.id,
            now,
        )
    document = service.get_document(session, document_id)
    audit.record(
        "document.uploaded",
        actor=user,
        target_type="document",
        target_id=document.id,
        case_id=case.id,
        details={"sizeBytes": document.size_bytes, "type": document.document_type},
    )
    response.headers["Location"] = f"/api/documents/{document_id}"
    return case_service.document_out(
        document, {user.id: user}, session.get(DocumentExtraction, document.id)
    )


def _content_disposition(document: Document, inline: bool) -> str:
    ascii_name = (
        document.name.encode("ascii", "ignore").decode().replace('"', "").replace("\\", "")
        or "document"
    )
    disposition = "inline" if inline else "attachment"
    return f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(document.name)}"


def _stream(handle: BinaryIO) -> Iterator[bytes]:
    with handle:
        while chunk := handle.read(READ_CHUNK):
            yield chunk


@router.get(
    "/documents/{document_id}/download",
    response_class=StreamingResponse,
    responses={
        200: {"description": "The stored file.", "content": {"application/octet-stream": {}}},
        **problem_responses(404),
    },
)
def download_document(
    document_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    storage: Storage = Depends(get_storage),
    audit: AuditLog = Depends(get_audit_log),
) -> StreamingResponse:
    """Download a stored file. Sample records have no file and return 404 ``no-file``."""
    document, case, _ = authz.load_document(
        session, user, service.parse_document_id(document_id), Action.VIEW, audit
    )
    return file_response(document, case.id, user, storage, audit)


def file_response(
    document: Document, case_id: uuid.UUID, user: User, storage: Storage, audit: AuditLog
) -> StreamingResponse:
    """The stored file with safe headers; the read is recorded in the audit log.

    Callers have already checked that ``user`` may read ``document``.
    """
    if document.storage_key is None or document.content_type is None:
        raise ProblemError(404, "no-file", "This is a sample record; it has no stored file.")
    if not storage.exists(document.storage_key):
        raise ProblemError(404, "file-missing", "The stored file could not be found.")

    kind = next((k for k in KINDS.values() if k.content_type == document.content_type), None)
    inline = bool(kind and kind.inline)
    media_type = document.content_type
    if media_type == "text/plain":
        media_type = "text/plain; charset=utf-8"
    headers = {
        "Content-Disposition": _content_disposition(document, inline),
        "Content-Length": str(document.size_bytes),
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
    }
    if inline and document.content_type != "application/pdf":
        # PDFs are excluded: browsers' built-in viewers refuse sandboxed documents.
        headers["Content-Security-Policy"] = SANDBOX_CSP
    # Access to case documents is recorded (who read which file, not its contents).
    audit.record(
        "document.downloaded",
        actor=user,
        target_type="document",
        target_id=document.id,
        case_id=case_id,
    )
    return StreamingResponse(
        _stream(storage.open(document.storage_key)), media_type=media_type, headers=headers
    )


@router.delete(
    "/documents/{document_id}",
    status_code=204,
    response_class=Response,
    responses=problem_responses(403, 404, 409),
)
def delete_document(
    document_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    now: datetime = Depends(get_now),
) -> Response:
    """Delete a document (Administrator or the lead advocate).

    The document leaves the case but is kept, with its file, until restored or
    purged by an operator (``python -m lexflow.cli.documents purge``).
    """
    document, case, _ = authz.load_document(
        session,
        user,
        service.parse_document_id(document_id),
        Action.DELETE_DOCUMENT,
        audit,
        lock=True,
    )
    service.soft_delete(session, document, by=user.id, now=now)
    audit.record(
        "document.deleted",
        actor=user,
        target_type="document",
        target_id=document.id,
        case_id=case.id,
    )
    return Response(status_code=204)


@router.post(
    "/documents/{document_id}/share",
    response_model=DocumentOut,
    responses=problem_responses(403, 404, 409, 422),
)
def share_document(
    document_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    now: datetime = Depends(get_now),
) -> DocumentOut:
    """Share a document with the case's client: it appears in their portal.

    Advocates on the case (and Administrators). Sample records cannot be
    shared (422 ``no-file``). Sharing it again changes nothing.
    """
    return _set_shared(document_id, True, user, session, audit, now)


@router.post(
    "/documents/{document_id}/unshare",
    response_model=DocumentOut,
    responses=problem_responses(403, 404, 409),
)
def unshare_document(
    document_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    now: datetime = Depends(get_now),
) -> DocumentOut:
    """Stop sharing a document with the client (it leaves their portal at once)."""
    return _set_shared(document_id, False, user, session, audit, now)


def _set_shared(
    document_id: str,
    share: bool,
    user: User,
    session: Session,
    audit: AuditLog,
    now: datetime,
) -> DocumentOut:
    document, case, _ = authz.load_document(
        session,
        user,
        service.parse_document_id(document_id),
        Action.SHARE_DOCUMENT,
        audit,
        lock=True,
    )
    if service.set_shared(session, document, share=share, by=user.id, now=now):
        audit.record(
            "document.shared" if share else "document.unshared",
            actor=user,
            target_type="document",
            target_id=document.id,
            case_id=case.id,
        )
    users = case_service.users_by_id(session, [document.uploaded_by_id])
    return case_service.document_out(document, users, session.get(DocumentExtraction, document.id))


@router.get(
    "/cases/{case_id}/documents/deleted",
    response_model=list[DeletedDocumentOut],
    responses=problem_responses(403, 404),
)
def list_deleted_documents(
    case_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
) -> list[DeletedDocumentOut]:
    """A case's deleted documents, most recently deleted first (Administrator or lead)."""
    case, _ = authz.load_case(
        session,
        user,
        case_service.parse_case_id(case_id),
        Action.VIEW_DELETED_DOCUMENTS,
        audit,
    )
    documents = service.deleted_documents(session, case.id)
    users = case_service.users_by_id(
        session, [d.uploaded_by_id for d in documents] + [d.deleted_by_id for d in documents]
    )
    jobs = case_service.extractions_for(session, (d.id for d in documents))
    return [case_service.deleted_document_out(d, users, jobs.get(d.id)) for d in documents]


@router.post(
    "/documents/{document_id}/restore",
    response_model=DocumentOut,
    responses=problem_responses(403, 404, 409),
)
def restore_document(
    document_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
) -> DocumentOut:
    """Put a deleted document back on its case (Administrator or the lead advocate).

    409 ``duplicate`` while another document on the case has the same name.
    Restoring a document that is not deleted changes nothing.
    """
    document, case, _ = authz.load_document(
        session,
        user,
        service.parse_document_id(document_id),
        Action.RESTORE_DOCUMENT,
        audit,
        include_deleted=True,
        lock=True,
    )
    if service.restore(session, document):
        audit.record(
            "document.restored",
            actor=user,
            target_type="document",
            target_id=document.id,
            case_id=case.id,
        )
    users = case_service.users_by_id(session, [document.uploaded_by_id])
    return case_service.document_out(document, users, session.get(DocumentExtraction, document.id))
