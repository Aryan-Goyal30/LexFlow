"""Searching a case's documents (staff on the case; not a legal-research feature).

``GET /api/cases/{case_id}/search?q=…&mode=keyword|semantic|hybrid&limit=10``

Who may search follows who may view the case (``authz.load_case``); Client
accounts never reach staff routes. Deleted documents are never searched. Each
search is audited with its mode and the number of results, never the query.
Semantic and hybrid searches need embeddings (``LEXFLOW_EMBEDDINGS=local``,
the model files and migration 0009); otherwise they answer 409 with the
reason, while keyword search still works.
"""

from __future__ import annotations

import threading
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from lexflow import authz
from lexflow.audit import AuditLog, get_audit_log
from lexflow.auth.deps import require_user
from lexflow.authz import Action
from lexflow.config import Settings, get_settings
from lexflow.db import get_session
from lexflow.embeddings import EmbeddingProvider, EmbeddingsUnavailableError, provider_for
from lexflow.errors import ProblemError, problem_responses
from lexflow.models import User
from lexflow.schemas import CaseSearchHitOut, CaseSearchOut
from lexflow.services import cases as case_service
from lexflow.services import retrieval

router = APIRouter(tags=["search"])

_lock = threading.Lock()
_loaded: dict[tuple[str, str, int], EmbeddingProvider | str] = {}


def get_search_provider(
    settings: Settings = Depends(get_settings),
) -> EmbeddingProvider | str:
    """The query embedder (loaded once, from local files only), or why there is none."""
    if settings.embeddings == "disabled":
        return "Semantic search is off: embeddings are disabled on this server."
    key = (settings.embedding_model, str(settings.model_dir), settings.embedding_threads)
    with _lock:
        if key not in _loaded:
            try:
                provider = provider_for(settings)
                _loaded[key] = provider if provider is not None else "Embeddings are disabled."
            except EmbeddingsUnavailableError as exc:
                return f"Semantic search is unavailable: {exc}"
        return _loaded[key]


def _unavailable(reason: str) -> ProblemError:
    return ProblemError(409, "semantic-search-unavailable", reason)


@router.get(
    "/cases/{case_id}/search",
    response_model=CaseSearchOut,
    responses=problem_responses(404, 409, 422),
)
def search_case(
    case_id: str,
    q: str = Query(min_length=1, max_length=retrieval.QUERY_MAX, description="What to look for."),
    mode: Literal["keyword", "semantic", "hybrid"] = Query(
        default="keyword", description="keyword (full text), semantic (embeddings) or hybrid."
    ),
    limit: int = Query(default=10, ge=1, le=50),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    provider: EmbeddingProvider | str = Depends(get_search_provider),
) -> CaseSearchOut:
    """Passages of this case's documents that match the query, best first.

    For staff who may view the case. Results come only from the case's own
    documents (not deleted, text extracted) and show where each passage is.
    They are ranked text, not legal advice or a prediction.
    """
    case, _ = authz.load_case(
        session, user, case_service.parse_case_id(case_id), Action.VIEW, audit
    )
    query = q.strip()
    if not query:
        raise ProblemError(422, "query-empty", "Type something to search for.")
    model: str | None = None
    if mode == "keyword":
        hits = retrieval.keyword(session, case.id, query, limit)
    else:
        if isinstance(provider, str):
            raise _unavailable(provider)
        if session.scalar(text("SELECT to_regclass('document_chunk_embeddings')")) is None:
            raise _unavailable("Semantic search is unavailable: migration 0009 is not applied.")
        model = provider.model
        search = retrieval.semantic if mode == "semantic" else retrieval.hybrid
        hits = search(session, provider, case.id, query, limit)
    cover = retrieval.coverage(session, case.id, model)
    audit.record(
        "case.searched",
        actor=user,
        target_type="case",
        target_id=case.id,
        case_id=case.id,
        details={"mode": mode, "results": len(hits), "limit": limit},
    )
    return CaseSearchOut(
        mode=mode,
        model=model,
        documents_with_text=cover.documents_with_text,
        documents_indexed=cover.documents_indexed,
        results=[
            CaseSearchHitOut(
                document_id=h.document_id,
                document_name=h.document_name,
                chunk_id=h.chunk_id,
                chunk_number=h.chunk_number,
                section_number=h.section_number,
                page_number=h.page_number,
                char_start=h.char_start,
                char_end=h.char_end,
                text=h.text,
                score=h.score,
            )
            for h in hits
        ],
    )
