"""Uploading, listing, downloading and deleting case documents."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import BinaryIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from lexflow.clock import get_today
from lexflow.db import get_session
from lexflow.errors import ProblemError, problem_responses
from lexflow.models import Document
from lexflow.schemas import DocumentOut
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
    session: Session = Depends(get_session),
    today: date = Depends(get_today),
) -> list[DocumentOut]:
    """The documents on a case, newest first."""
    detail = case_service.get_case_detail(session, case_service.parse_case_id(case_id), today)
    return detail.documents


@router.post(
    "/cases/{case_id}/documents",
    response_model=DocumentOut,
    status_code=201,
    responses=problem_responses(404, 409, 413, 415, 422),
)
def upload_document(
    case_id: str,
    response: Response,
    file: UploadFile = File(description="One file: PDF, Word, text, PNG, JPG, GIF or WebP."),
    session: Session = Depends(get_session),
    storage: Storage = Depends(get_storage),
    limit: int = Depends(get_upload_limit),
    today: date = Depends(get_today),
) -> DocumentOut:
    """Attach one file to a case.

    The file's real content must match its extension. Errors carry a ``code``:
    ``unsupported-type``, ``content-mismatch``, ``empty``, ``duplicate``,
    ``too-large`` or ``invalid-name``.
    """
    # A plain def: FastAPI runs it in the thread pool, so its database and file
    # work never blocks the event loop (and other requests) while it runs.
    document_id = service.upload_document(
        session, storage, case_service.parse_case_id(case_id), file, limit, today
    )
    response.headers["Location"] = f"/api/documents/{document_id}"
    return case_service.document_out(service.get_document(session, document_id))


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
    session: Session = Depends(get_session),
    storage: Storage = Depends(get_storage),
) -> StreamingResponse:
    """Download a stored file. Sample records have no file and return 404 ``no-file``."""
    document = service.get_document(session, service.parse_document_id(document_id))
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
    return StreamingResponse(
        _stream(storage.open(document.storage_key)), media_type=media_type, headers=headers
    )


@router.delete(
    "/documents/{document_id}",
    status_code=204,
    response_class=Response,
    responses=problem_responses(404),
)
def delete_document(
    document_id: str,
    session: Session = Depends(get_session),
    storage: Storage = Depends(get_storage),
) -> Response:
    """Remove a document and its stored file."""
    service.delete_document(session, storage, service.parse_document_id(document_id))
    return Response(status_code=204)
