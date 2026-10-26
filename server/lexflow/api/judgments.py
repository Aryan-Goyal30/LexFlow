"""The judgment collection: browse, search, read (Phase 4; staff only).

Judgments are firm-wide reference material, so every staff role may use
these routes; Client accounts never reach them (the staff router refuses
them) and anonymous callers get 401. Nothing here changes the collection:
judgments are imported only from the command line (``lexflow.cli.judgments``).
Searches are audited with their mode, page and result count, never the
query. Results are passages of stored judgments ranked by similarity: no
legal conclusion is drawn and nothing is generated.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from lexflow.api.search import get_search_provider
from lexflow.audit import AuditLog, get_audit_log
from lexflow.auth.deps import require_user
from lexflow.db import get_session
from lexflow.embeddings import EmbeddingProvider
from lexflow.errors import ProblemError, problem_responses
from lexflow.models import Judgment, JudgmentSource, User
from lexflow.schemas import (
    JudgmentDatasetOut,
    JudgmentDetailOut,
    JudgmentFacetsOut,
    JudgmentHitOut,
    JudgmentPageOut,
    JudgmentPassageOut,
    JudgmentProvenanceOut,
    JudgmentSearchModesOut,
    JudgmentSearchOut,
    JudgmentSourceOut,
    JudgmentSummaryOut,
    JudgmentTextOut,
    JudgmentTextSectionOut,
)
from lexflow.services import judgments as service

router = APIRouter(tags=["judgments"])

SEARCH_PAGE_MAX = 20
SEARCH_PAGES = service.MAX_RESULTS // 10


def _summary(judgment: Judgment, source: JudgmentSource) -> JudgmentSummaryOut:
    return JudgmentSummaryOut(
        id=judgment.id,
        title=judgment.title,
        court=judgment.court,
        citation=judgment.citation,
        decision_date=judgment.decision_date,
        year=judgment.year,
        practice_areas=list(judgment.practice_areas),
        source_name=source.name,
        source_url=judgment.source_url,
        synthetic=source.is_synthetic,
    )


def _filters(
    court: str | None,
    year_from: int | None,
    year_to: int | None,
    origin: service.Origin | None = None,
) -> service.Filters:
    if year_from is not None and year_to is not None and year_from > year_to:
        raise ProblemError(422, "invalid-years", "yearFrom must not be after yearTo.")
    return service.Filters(
        court=court.strip() if court else None,
        year_from=year_from,
        year_to=year_to,
        origin=origin,
    )


def _modes(provider: EmbeddingProvider | str) -> JudgmentSearchModesOut:
    if isinstance(provider, str):
        return JudgmentSearchModesOut(
            keyword=True, semantic=False, hybrid=False, unavailable_reason=provider, model=None
        )
    return JudgmentSearchModesOut(
        keyword=True, semantic=True, hybrid=True, unavailable_reason=None, model=provider.model
    )


Court = Query(default=None, max_length=200, description="Only this court (exact name).")
YearFrom = Query(default=None, ge=1800, le=2100, alias="yearFrom")
YearTo = Query(default=None, ge=1800, le=2100, alias="yearTo")
OriginFilter = Query(
    default=None,
    description="genuine: from real sources only; synthetic: invented test data only.",
)


@router.get("/judgments/facets", response_model=JudgmentFacetsOut)
def judgment_facets(
    session: Session = Depends(get_session),
    provider: EmbeddingProvider | str = Depends(get_search_provider),
) -> JudgmentFacetsOut:
    """Totals, courts and years in the collection, and which search modes work."""
    modes = _modes(provider)
    found = service.facets(session, modes.model)
    return JudgmentFacetsOut(
        total=found.total,
        synthetic=found.synthetic,
        indexed=found.indexed,
        courts=found.courts,
        year_min=found.year_min,
        year_max=found.year_max,
        modes=modes,
    )


@router.get("/judgments", response_model=JudgmentPageOut, responses=problem_responses(422))
def list_judgments(
    court: str | None = Court,
    year_from: int | None = YearFrom,
    year_to: int | None = YearTo,
    origin: service.Origin | None = OriginFilter,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=50, alias="pageSize"),
    session: Session = Depends(get_session),
) -> JudgmentPageOut:
    """The collection, newest decision first (undated last), with stable paging."""
    filters = _filters(court, year_from, year_to, origin)
    rows = session.execute(
        service.browse_query(filters).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return JudgmentPageOut(
        items=[_summary(judgment, source) for judgment, source in rows],
        total=service.count(session, filters),
        page=page,
        page_size=page_size,
    )


@router.get(
    "/judgments/search", response_model=JudgmentSearchOut, responses=problem_responses(409, 422)
)
def search_judgments(
    q: str = Query(min_length=1, max_length=service.QUERY_MAX, description="What to look for."),
    mode: Literal["keyword", "semantic", "hybrid"] = Query(default="keyword"),
    court: str | None = Court,
    year_from: int | None = YearFrom,
    year_to: int | None = YearTo,
    origin: service.Origin | None = OriginFilter,
    page: int = Query(default=1, ge=1, le=SEARCH_PAGES),
    page_size: int = Query(default=10, ge=1, le=SEARCH_PAGE_MAX, alias="pageSize"),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    provider: EmbeddingProvider | str = Depends(get_search_provider),
) -> JudgmentSearchOut:
    """Judgments ranked by their best passage for the query (at most 100), paged.

    409 ``semantic-search-unavailable`` (with the reason) for semantic or
    hybrid search when embeddings cannot run; keyword search always works.
    """
    query = q.strip()
    if not query:
        raise ProblemError(422, "query-empty", "Type something to search for.")
    filters = _filters(court, year_from, year_to, origin)
    active: EmbeddingProvider | None = None
    if mode != "keyword":
        if isinstance(provider, str):
            raise ProblemError(409, "semantic-search-unavailable", provider)
        active = provider
    ranked, keyword_match = service.search_with_match(session, mode, query, filters, active)
    window = ranked[(page - 1) * page_size : page * page_size]
    found = service.judgments_by_id(session, [hit.judgment_id for hit in window])
    audit.record(
        "judgment.searched",
        actor=user,
        target_type="judgment",
        details={"mode": mode, "results": len(ranked), "page": page},
    )
    return JudgmentSearchOut(
        mode=mode,
        model=active.model if active else None,
        keyword_match=keyword_match,
        total=len(ranked),
        max_results=service.MAX_RESULTS,
        page=page,
        page_size=page_size,
        results=[
            JudgmentHitOut(
                judgment=_summary(*found[hit.judgment_id]),
                score=hit.score,
                passage=JudgmentPassageOut(
                    chunk_id=hit.passage.chunk_id,
                    section_number=hit.passage.section_number,
                    page_number=hit.passage.page_number,
                    char_start=hit.passage.char_start,
                    char_end=hit.passage.char_end,
                    text=hit.passage.text,
                ),
            )
            for hit in window
            if hit.judgment_id in found
        ],
    )


@router.get(
    "/judgments/{judgment_id}", response_model=JudgmentDetailOut, responses=problem_responses(404)
)
def get_judgment(judgment_id: str, session: Session = Depends(get_session)) -> JudgmentDetailOut:
    """One judgment with its source, the source's terms record and its provenance."""
    judgment, source = service.get(session, judgment_id)
    recorded = service.provenance(session, judgment.id)
    return JudgmentDetailOut(
        **_summary(judgment, source).model_dump(),
        bench=judgment.bench,
        source=JudgmentSourceOut(
            key=source.key,
            name=source.name,
            terms_url=source.terms_url,
            terms_checked_on=source.terms_checked_on,
            terms_checked_by=source.terms_checked_by,
            permitted_use=source.permitted_use,
            synthetic=source.is_synthetic,
        ),
        provenance=None
        if recorded is None
        else JudgmentProvenanceOut(
            neutral_citation=recorded.neutral_citation,
            attribution=recorded.attribution,
            dataset=JudgmentDatasetOut.model_validate(recorded.dataset)
            if recorded.dataset
            else None,
            source_record={
                k: v for k, v in recorded.source_record.items() if isinstance(v, str | int)
            },
            recorded_at=recorded.recorded_at,
        ),
        page_count=judgment.page_count,
        section_count=judgment.section_count,
        char_count=judgment.char_count,
        extractor=judgment.extractor,
        imported_at=judgment.imported_at,
    )


@router.get(
    "/judgments/{judgment_id}/text",
    response_model=JudgmentTextOut,
    responses=problem_responses(404),
)
def judgment_text(
    judgment_id: str,
    section: int = Query(default=1, ge=1, description="The page (PDF) or part to read."),
    session: Session = Depends(get_session),
) -> JudgmentTextOut:
    """One page (or part) of a judgment's text, exactly as extracted."""
    judgment, source = service.get(session, judgment_id)
    found = service.section(session, judgment, section)
    return JudgmentTextOut(
        judgment_id=judgment.id,
        title=judgment.title,
        synthetic=source.is_synthetic,
        page_count=judgment.page_count,
        section_count=judgment.section_count,
        section=JudgmentTextSectionOut(
            number=found.number, page_number=found.page_number, text=found.text
        ),
    )
