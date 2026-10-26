"""The judgment collection: browsing, searching, reading and indexing (Phase 4).

Search ranks **judgments** by their best passage:

- keyword: PostgreSQL full-text search over chunks (``english``,
  ``websearch_to_tsquery``, the stored ``search_vector`` with its GIN index),
  scored by ``ts_rank_cd``. A passage must contain every word; only when no
  passage does, keyword mode falls back to passages containing **any** of
  the words (ranked by how well they cover them), and says so (``Match``).
  On the genuine corpus, 14 of 17 described-issue queries found nothing
  with every word required (docs/verification/batch2/evaluation). Hybrid
  mode uses every-word matches only (see ``hybrid_with_match``);
- semantic: exact cosine similarity of the query (embedded by the Phase 3
  model with its query instruction) to chunk vectors of the current model and
  current text;
- hybrid: both judgment rankings merged by reciprocal-rank fusion (k = 60).

At most ``MAX_RESULTS`` judgments are ranked per query (bounded candidate
lists), then paged. Ties break on the judgment id, then the chunk number, so
the same query always gives the same order. Every result carries the passage
with its page and exact offsets. Results are passages of stored judgments,
ranked by similarity; they are not legal conclusions.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import (
    ColumnElement,
    Select,
    Text,
    and_,
    cast,
    delete,
    func,
    literal_column,
    select,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import TSQUERY, insert
from sqlalchemy.orm import Session

from lexflow.embeddings import EmbeddingProvider
from lexflow.errors import ProblemError
from lexflow.models import (
    Judgment,
    JudgmentChunk,
    JudgmentChunkEmbedding,
    JudgmentProvenance,
    JudgmentSection,
    JudgmentSource,
)

Mode = Literal["keyword", "semantic", "hybrid"]
Match = Literal["all", "any"]  # keyword words required: every one, or any
Origin = Literal["genuine", "synthetic"]
MAX_RESULTS = 100
RRF_K = 60
QUERY_MAX = 300
JUDGMENT_NOT_FOUND = "No judgment with this id exists."


@dataclass(frozen=True)
class Filters:
    court: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    # "genuine": from a real source; "synthetic": invented test data (Batch 2).
    origin: Origin | None = None

    def condition(self) -> ColumnElement[bool]:
        parts: list[ColumnElement[bool]] = [true()]
        if self.court:
            parts.append(Judgment.court == self.court)
        if self.year_from is not None:
            parts.append(Judgment.year >= self.year_from)
        if self.year_to is not None:
            parts.append(Judgment.year <= self.year_to)
        if self.origin is not None:
            sources = select(JudgmentSource.id).where(
                JudgmentSource.is_synthetic.is_(self.origin == "synthetic")
            )
            parts.append(Judgment.source_id.in_(sources))
        return and_(*parts)


@dataclass(frozen=True)
class Passage:
    chunk_id: uuid.UUID
    chunk_number: int
    section_number: int
    page_number: int | None
    char_start: int
    char_end: int
    text: str


@dataclass(frozen=True)
class Ranked:
    judgment_id: uuid.UUID
    score: float
    passage: Passage


def parse_judgment_id(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise ProblemError(404, "judgment-not-found", JUDGMENT_NOT_FOUND) from None


def _best_per_judgment(rows: Sequence[tuple[JudgmentChunk, float]], limit: int) -> list[Ranked]:
    """Rows come best first (ties already broken); keep each judgment's first."""
    ranked: list[Ranked] = []
    seen: set[uuid.UUID] = set()
    for chunk, score in rows:
        if chunk.judgment_id in seen:
            continue
        seen.add(chunk.judgment_id)
        ranked.append(
            Ranked(
                chunk.judgment_id,
                float(score),
                Passage(
                    chunk.id,
                    chunk.number,
                    chunk.section_number,
                    chunk.page_number,
                    chunk.char_start,
                    chunk.char_end,
                    chunk.text,
                ),
            )
        )
        if len(ranked) == limit:
            break
    return ranked


def _tsquery(query: str, match: Match) -> ColumnElement[Any]:
    english: ColumnElement[Any] = literal_column("'english'::regconfig")
    if match == "all":
        return func.websearch_to_tsquery(english, query)
    # The same words (stemmed, stop words dropped), any of them: the
    # plainto_tsquery terms joined by OR instead of AND.
    anded = cast(func.plainto_tsquery(english, query), Text)
    return cast(func.replace(anded, "&", "|"), TSQUERY)


def keyword(
    session: Session,
    query: str,
    filters: Filters,
    limit: int = MAX_RESULTS,
    *,
    match: Match = "all",
) -> list[Ranked]:
    tsquery = _tsquery(query, match)
    rank = func.ts_rank_cd(JudgmentChunk.search_vector, tsquery)
    # The best chunk of each judgment first (DISTINCT ON), then judgments by score.
    best = (
        select(JudgmentChunk.id.label("chunk_id"), rank.label("score"), JudgmentChunk.judgment_id)
        .join(Judgment, Judgment.id == JudgmentChunk.judgment_id)
        .where(JudgmentChunk.search_vector.op("@@")(tsquery), filters.condition())
        .order_by(JudgmentChunk.judgment_id, rank.desc(), JudgmentChunk.number)
        .distinct(JudgmentChunk.judgment_id)
        .subquery()
    )
    rows = session.execute(
        select(JudgmentChunk, best.c.score)
        .join(best, best.c.chunk_id == JudgmentChunk.id)
        .order_by(best.c.score.desc(), best.c.judgment_id)
        .limit(limit)
    ).all()
    return _best_per_judgment([(c, s) for c, s in rows], limit)


def semantic(
    session: Session,
    provider: EmbeddingProvider,
    query: str,
    filters: Filters,
    limit: int = MAX_RESULTS,
) -> list[Ranked]:
    vector = provider.embed_query(query)
    if len(vector) != provider.dimensions:
        raise ValueError("the query vector has the wrong number of dimensions")
    distance = JudgmentChunkEmbedding.embedding.cosine_distance(vector)
    best = (
        select(
            JudgmentChunk.id.label("chunk_id"),
            (1 - distance).label("score"),
            JudgmentChunk.judgment_id,
        )
        .join(
            JudgmentChunkEmbedding,
            and_(
                JudgmentChunkEmbedding.chunk_id == JudgmentChunk.id,
                JudgmentChunkEmbedding.model == provider.model,
                JudgmentChunkEmbedding.content_sha256 == JudgmentChunk.content_sha256,
            ),
        )
        .join(Judgment, Judgment.id == JudgmentChunk.judgment_id)
        .where(filters.condition())
        .order_by(JudgmentChunk.judgment_id, distance, JudgmentChunk.number)
        .distinct(JudgmentChunk.judgment_id)
        .subquery()
    )
    rows = session.execute(
        select(JudgmentChunk, best.c.score)
        .join(best, best.c.chunk_id == JudgmentChunk.id)
        .order_by(best.c.score.desc(), best.c.judgment_id)
        .limit(limit)
    ).all()
    return _best_per_judgment([(c, s) for c, s in rows], limit)


def hybrid(
    session: Session,
    provider: EmbeddingProvider,
    query: str,
    filters: Filters,
    limit: int = MAX_RESULTS,
) -> list[Ranked]:
    return hybrid_with_match(session, provider, query, filters, limit)[0]


def keyword_with_fallback(
    session: Session, query: str, filters: Filters, limit: int = MAX_RESULTS
) -> tuple[list[Ranked], Match]:
    """Every word required; if nothing matches, any word (and which was used)."""
    strict = keyword(session, query, filters, limit, match="all")
    if strict:
        return strict, "all"
    return keyword(session, query, filters, limit, match="any"), "any"


def hybrid_with_match(
    session: Session,
    provider: EmbeddingProvider,
    query: str,
    filters: Filters,
    limit: int = MAX_RESULTS,
) -> tuple[list[Ranked], Match]:
    # Strict keyword matches only: fusing the any-word fallback with semantic
    # ranking lowered hybrid MRR on both Batch 2 evaluation sets (0.971 -> 0.683
    # and 0.505 -> 0.474), so hybrid keeps every-word keyword matches.
    fused: dict[uuid.UUID, tuple[float, Ranked]] = {}
    match: Match = "all"
    lists = (
        keyword(session, query, filters, limit, match=match),
        semantic(session, provider, query, filters, limit),
    )
    for results in lists:
        for rank, hit in enumerate(results, start=1):
            score, first = fused.get(hit.judgment_id, (0.0, hit))
            fused[hit.judgment_id] = (score + 1 / (RRF_K + rank), first)
    ordered = sorted(fused.values(), key=lambda pair: (-pair[0], str(pair[1].judgment_id)))
    return [Ranked(hit.judgment_id, score, hit.passage) for score, hit in ordered[:limit]], match


def search(
    session: Session,
    mode: Mode,
    query: str,
    filters: Filters,
    provider: EmbeddingProvider | None,
) -> list[Ranked]:
    return search_with_match(session, mode, query, filters, provider)[0]


def search_with_match(
    session: Session,
    mode: Mode,
    query: str,
    filters: Filters,
    provider: EmbeddingProvider | None,
) -> tuple[list[Ranked], Match | None]:
    """The ranking, and for keyword and hybrid whether every word or any was required."""
    if mode == "keyword":
        return keyword_with_fallback(session, query, filters)
    if provider is None:  # the caller checks availability first
        raise ValueError("semantic search needs an embedding provider")
    if mode == "semantic":
        return semantic(session, provider, query, filters), None
    return hybrid_with_match(session, provider, query, filters)


def judgments_by_id(
    session: Session, ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, tuple[Judgment, JudgmentSource]]:
    if not ids:
        return {}
    rows = session.execute(
        select(Judgment, JudgmentSource)
        .join(JudgmentSource, JudgmentSource.id == Judgment.source_id)
        .where(Judgment.id.in_(ids))
    ).all()
    return {judgment.id: (judgment, source) for judgment, source in rows}


def browse_query(filters: Filters) -> Select[tuple[Judgment, JudgmentSource]]:
    """The collection in a stable order: newest decision first, undated last."""
    return (
        select(Judgment, JudgmentSource)
        .join(JudgmentSource, JudgmentSource.id == Judgment.source_id)
        .where(filters.condition())
        .order_by(
            Judgment.decision_date.desc().nulls_last(),
            Judgment.year.desc().nulls_last(),
            Judgment.title,
            Judgment.id,
        )
    )


def count(session: Session, filters: Filters) -> int:
    return int(
        session.scalar(select(func.count()).select_from(Judgment).where(filters.condition())) or 0
    )


def get(session: Session, raw_id: str) -> tuple[Judgment, JudgmentSource]:
    found = judgments_by_id(session, [parse_judgment_id(raw_id)])
    if not found:
        raise ProblemError(404, "judgment-not-found", JUDGMENT_NOT_FOUND)
    return next(iter(found.values()))


def provenance(session: Session, judgment_id: uuid.UUID) -> JudgmentProvenance | None:
    """The judgment's provenance record, if it has one (format-2 imports, migration 0014)."""
    if session.scalar(text("SELECT to_regclass('judgment_provenance')")) is None:
        return None
    return session.get(JudgmentProvenance, judgment_id)


def section(session: Session, judgment: Judgment, number: int) -> JudgmentSection:
    found = session.get(JudgmentSection, (judgment.id, number))
    if found is None:
        unit = "page" if judgment.page_count is not None else "part"
        raise ProblemError(
            404,
            "section-not-found",
            f"This judgment has {judgment.section_count} {unit}"
            f"{'' if judgment.section_count == 1 else 's'}.",
        )
    return found


@dataclass(frozen=True)
class Facets:
    total: int
    synthetic: int
    indexed: int
    courts: list[str]
    year_min: int | None
    year_max: int | None


def facets(session: Session, model: str | None) -> Facets:
    total = int(session.scalar(select(func.count()).select_from(Judgment)) or 0)
    synthetic = int(
        session.scalar(
            select(func.count())
            .select_from(Judgment)
            .join(JudgmentSource, JudgmentSource.id == Judgment.source_id)
            .where(JudgmentSource.is_synthetic)
        )
        or 0
    )
    indexed = (
        int(
            session.scalar(
                select(func.count())
                .select_from(Judgment)
                .where(Judgment.index_status == "indexed", Judgment.embedding_model == model)
            )
            or 0
        )
        if model
        else 0
    )
    courts = list(session.scalars(select(Judgment.court).distinct().order_by(Judgment.court)))
    year_min, year_max = session.execute(
        select(func.min(Judgment.year), func.max(Judgment.year))
    ).one()
    return Facets(total, synthetic, indexed, courts, year_min, year_max)


# --- indexing (explicit command only) -------------------------------------------------------


def needing_vectors(session: Session, model: str) -> list[tuple[uuid.UUID, str]]:
    """Judgments without current vectors for ``model`` (never, failed, other model)."""
    return [
        (judgment_id, title)
        for judgment_id, title in session.execute(
            select(Judgment.id, Judgment.title)
            .where(
                (Judgment.index_status != "indexed")
                | (Judgment.embedding_model != model)
                | Judgment.embedding_model.is_(None)
            )
            .order_by(Judgment.title, Judgment.id)
        )
    ]


def index_judgment(
    session: Session,
    provider: EmbeddingProvider,
    judgment_id: uuid.UUID,
    *,
    batch_size: int,
    now: Callable[[], datetime],
) -> int:
    """Embed the judgment's chunks lacking a current vector; commits per batch.

    Returns how many chunks were embedded. On failure the judgment is marked
    ``failed`` (vectors already committed stay) and the error is raised.
    """
    chunks = session.execute(
        select(JudgmentChunk.id, JudgmentChunk.text, JudgmentChunk.content_sha256)
        .where(JudgmentChunk.judgment_id == judgment_id)
        .order_by(JudgmentChunk.number)
    ).all()
    current: dict[uuid.UUID, str] = {
        chunk_id: sha
        for chunk_id, sha in session.execute(
            select(JudgmentChunkEmbedding.chunk_id, JudgmentChunkEmbedding.content_sha256).where(
                JudgmentChunkEmbedding.judgment_id == judgment_id,
                JudgmentChunkEmbedding.model == provider.model,
            )
        )
    }
    todo = [c for c in chunks if current.get(c.id) != c.content_sha256]
    embedded = 0
    try:
        for start in range(0, len(todo), batch_size):
            batch = todo[start : start + batch_size]
            vectors = provider.embed_passages([c.text for c in batch])
            if len(vectors) != len(batch) or any(len(v) != provider.dimensions for v in vectors):
                raise ValueError("the model returned vectors of the wrong number or size")
            statement = insert(JudgmentChunkEmbedding).values(
                [
                    {
                        "chunk_id": c.id,
                        "model": provider.model,
                        "judgment_id": judgment_id,
                        "content_sha256": c.content_sha256,
                        "dimensions": provider.dimensions,
                        "embedding": vector,
                    }
                    for c, vector in zip(batch, vectors, strict=True)
                ]
            )
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=["chunk_id", "model"],
                    set_={
                        "content_sha256": statement.excluded.content_sha256,
                        "embedding": statement.excluded.embedding,
                    },
                )
            )
            session.commit()
            embedded += len(batch)
    except Exception:
        session.rollback()
        judgment = session.get(Judgment, judgment_id)
        if judgment is not None:
            judgment.index_status = "failed"
            session.commit()
        raise
    session.execute(
        delete(JudgmentChunkEmbedding).where(
            JudgmentChunkEmbedding.judgment_id == judgment_id,
            JudgmentChunkEmbedding.model != provider.model,
        )
    )
    judgment = session.get(Judgment, judgment_id)
    if judgment is not None:
        judgment.index_status = "indexed"
        judgment.embedding_model = provider.model
        judgment.indexed_at = now()
    session.commit()
    return embedded
