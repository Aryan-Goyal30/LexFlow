"""The client portal (Client accounts only): their cases, hearings and shared documents.

Mounted with ``require_roles(CLIENT)``: staff accounts get 403 here, as Client
accounts do on every staff route. See ``lexflow.services.portal`` for what a
client may see.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from lexflow.api.documents import file_response
from lexflow.audit import AuditLog, get_audit_log
from lexflow.auth.deps import require_user
from lexflow.clock import get_today
from lexflow.db import get_session
from lexflow.errors import ProblemError, problem_responses
from lexflow.models import User
from lexflow.schemas import PortalCaseDetail, PortalCaseSummary
from lexflow.services import portal as service
from lexflow.storage import Storage, get_storage

router = APIRouter(prefix="/portal", tags=["client portal"])


def _uuid(raw: str, code: str, detail: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise ProblemError(404, code, detail) from None


@router.get("/cases", response_model=list[PortalCaseSummary])
def list_cases(
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    today: date = Depends(get_today),
) -> list[PortalCaseSummary]:
    """Your cases (archived ones are not shown), newest first."""
    return service.list_cases(session, user, today)


@router.get("/cases/{case_id}", response_model=PortalCaseDetail, responses=problem_responses(404))
def get_case(
    case_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    today: date = Depends(get_today),
) -> PortalCaseDetail:
    """One of your cases, with its coming hearings and the documents shared with you."""
    parsed = _uuid(case_id, "case-not-found", service.CASE_NOT_FOUND)
    return service.get_case(session, user, parsed, today)


@router.get(
    "/documents/{document_id}/download",
    response_class=StreamingResponse,
    responses={
        200: {"description": "The shared file.", "content": {"application/octet-stream": {}}},
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
    """Download a document shared with you. Anything else answers 404."""
    parsed = _uuid(document_id, "document-not-found", service.DOCUMENT_NOT_FOUND)
    document = service.shared_document(session, user, parsed)
    return file_response(document, document.case_id, user, storage, audit)
