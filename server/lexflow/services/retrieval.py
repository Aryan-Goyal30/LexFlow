"""Searching a case's extracted text: keyword, semantic (pgvector) and hybrid.

Searches stay inside one case, which the caller has already been allowed to
view (``authz.load_case``). Only chunks of documents that are not deleted and
whose text is ready are searched; a semantic result also needs a vector made
by the current model from the chunk's current text. Every result carries the
document, chunk, page (for PDFs) and exact character offsets, so the passage
can be found in the extracted text. Results are passages from the case's own
documents, ranked by similarity; they are not legal conclusions.

- keyword: PostgreSQL full-text search (``english`` configuration,
  ``websearch_to_tsquery``), ranked by ``ts_rank_cd``.
- semantic: the query embedded by the same model (with its query
  instruction), ranked by cosine similarity; exact, no approximate index.
- hybrid: both lists merged by reciprocal-rank fusion (k = 60).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from typing import Literal

from sqlalchemy import ColumnElement, Select, and_, func, literal_column, select
from sqlalchemy.orm import Session

from lexflow.embeddings import EmbeddingProvider
from lexflow.models import Document, DocumentChunk, DocumentChunkEmbedding, DocumentExtraction

Mode = Literal["keyword", "semantic", "hybrid"]
RRF_K = 60
QUERY_MAX = 500


@dataclass(frozen=True)
class Hit:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    chunk_number: int
    section_number: int
    page_number: int | None
    char_start: int
    char_end: int
    text: str
    score: float


def _searchable(case_id: uuid.UUID) -> ColumnElement[bool]:
    """Conditions shared by every mode: this case, live documents, text ready."""
    return and_(
        Document.case_id == case_id,
        Document.deleted_at.is_(None),
        DocumentExtraction.status == "ready",
    )


def _chunks() -> Select[tuple[DocumentChunk, str]]:
    return (
        select(DocumentChunk, Document.name)
        .join(Document, Document.id == DocumentChunk.document_id)
        .join(DocumentExtraction, DocumentExtraction.document_id == Document.id)
    )


def _hit(chunk: DocumentChunk, name: str, score: float) -> Hit:
    return Hit(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        document_name=name,
        chunk_number=chunk.number,
        section_number=chunk.section_number,
        page_number=chunk.page_number,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        text=chunk.text,
        score=float(score),
    )


def keyword(session: Session, case_id: uuid.UUID, query: str, limit: int) -> list[Hit]:
    tsquery = func.websearch_to_tsquery(literal_column("'english'"), query)
    vector = func.to_tsvector(literal_column("'english'"), DocumentChunk.text)
    rank = func.ts_rank_cd(vector, tsquery)
    rows = session.execute(
        _chunks()
        .add_columns(rank.label("rank"))
        .where(_searchable(case_id), vector.op("@@")(tsquery))
        .order_by(rank.desc(), DocumentChunk.document_id, DocumentChunk.number)
        .limit(limit)
    ).all()
    return [_hit(chunk, name, score) for chunk, name, score in rows]


def semantic(
    session: Session,
    provider: EmbeddingProvider,
    case_id: uuid.UUID,
    query: str,
    limit: int,
) -> list[Hit]:
    vector = provider.embed_query(query)
    if len(vector) != provider.dimensions:
        raise ValueError("the query vector has the wrong number of dimensions")
    distance = DocumentChunkEmbedding.embedding.cosine_distance(vector)
    rows = session.execute(
        _chunks()
        .join(
            DocumentChunkEmbedding,
            and_(
                DocumentChunkEmbedding.chunk_id == DocumentChunk.id,
                DocumentChunkEmbedding.model == provider.model,
                DocumentChunkEmbedding.content_sha256 == DocumentChunk.content_sha256,
            ),
        )
        .add_columns((1 - distance).label("similarity"))
        .where(_searchable(case_id))
        .order_by(distance, DocumentChunk.document_id, DocumentChunk.number)
        .limit(limit)
    ).all()
    return [_hit(chunk, name, score) for chunk, name, score in rows]


def hybrid(
    session: Session,
    provider: EmbeddingProvider,
    case_id: uuid.UUID,
    query: str,
    limit: int,
) -> list[Hit]:
    depth = min(max(limit * 4, 20), 100)
    fused: dict[uuid.UUID, tuple[float, Hit]] = {}
    for hits in (
        keyword(session, case_id, query, depth),
        semantic(session, provider, case_id, query, depth),
    ):
        for rank, hit in enumerate(hits, start=1):
            score, _ = fused.get(hit.chunk_id, (0.0, hit))
            fused[hit.chunk_id] = (score + 1 / (RRF_K + rank), hit)
    ranked = sorted(fused.values(), key=lambda pair: (-pair[0], str(pair[1].chunk_id)))
    return [replace(hit, score=score) for score, hit in ranked[:limit]]


@dataclass(frozen=True)
class Coverage:
    documents_with_text: int
    documents_indexed: int


def coverage(session: Session, case_id: uuid.UUID, model: str | None) -> Coverage:
    """How many of the case's live documents have text, and vectors for ``model``."""
    base = (
        select(func.count())
        .select_from(DocumentExtraction)
        .join(Document, Document.id == DocumentExtraction.document_id)
        .where(_searchable(case_id))
    )
    with_text = session.scalar(base) or 0
    indexed = (
        session.scalar(
            base.where(
                DocumentExtraction.index_status == "indexed",
                DocumentExtraction.embedding_model == model,
            )
        )
        if model
        else 0
    )
    return Coverage(int(with_text), int(indexed or 0))
