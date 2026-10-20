"""Embedding the chunks of extracted documents (when embeddings are enabled).

A document waits for indexing when its extraction job is ``ready`` with
``index_status = 'pending'`` (set when its text was stored with embeddings
enabled, or by ``python -m lexflow.cli.models queue-indexing``).

``index_next`` takes one such document under a per-document advisory lock
(held by its own database connection, so it is released if the worker dies),
embeds the chunks that have no vector yet for the current model, or whose
text changed, in bounded batches, and commits after each batch. A retry after
a crash or failure therefore skips what is already stored. On success the job
records the model and the time; vectors of other models for that document are
removed. On failure the job is marked ``failed`` with the reason and is not
retried automatically (``queue-indexing`` or extracting the text again does).

If the document's text was extracted again while it was being indexed, its
old chunks (and their vectors) are gone and the result is discarded; the new
text is indexed on its own turn.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Engine, delete, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from lexflow.embeddings import EmbeddingProvider
from lexflow.models import DocumentChunk, DocumentChunkEmbedding, DocumentExtraction

logger = logging.getLogger("lexflow.worker")

REASON_MAX = 500
LOCK_KEY = "SELECT hashtextextended('lexflow.index:' || CAST(:id AS text), 0)"


@dataclass(frozen=True)
class IndexResult:
    document_id: uuid.UUID
    status: str  # "indexed", "failed" or "discarded"
    embedded: int  # chunks embedded in this run
    reused: int  # chunks that already had a current vector


def pending_documents(session: Session, limit: int = 20) -> list[uuid.UUID]:
    return list(
        session.scalars(
            select(DocumentExtraction.document_id)
            .where(
                DocumentExtraction.status == "ready",
                DocumentExtraction.index_status == "pending",
            )
            .order_by(DocumentExtraction.updated_at, DocumentExtraction.document_id)
            .limit(limit)
        )
    )


def index_next(
    engine: Engine,
    provider: EmbeddingProvider,
    *,
    batch_size: int,
    now: Callable[[], datetime],
) -> IndexResult | None:
    """Index one waiting document; ``None`` when nothing is waiting (or all are locked)."""
    with Session(engine) as session:
        candidates = pending_documents(session)
    for document_id in candidates:
        with engine.connect() as connection:
            key = connection.scalar(text(LOCK_KEY), {"id": str(document_id)})
            if not connection.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": key}):
                connection.rollback()
                continue  # another worker has it
            connection.commit()
            try:
                with Session(bind=connection) as session:
                    return index_document(
                        session, provider, document_id, batch_size=batch_size, now=now
                    )
            finally:
                connection.rollback()
                connection.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})
                connection.commit()
    return None


def _job_marker(session: Session, document_id: uuid.UUID) -> tuple[str, str, object] | None:
    row = session.execute(
        select(
            DocumentExtraction.status,
            DocumentExtraction.index_status,
            DocumentExtraction.finished_at,
        ).where(DocumentExtraction.document_id == document_id)
    ).one_or_none()
    return None if row is None else (row[0], row[1], row[2])


def index_document(
    session: Session,
    provider: EmbeddingProvider,
    document_id: uuid.UUID,
    *,
    batch_size: int,
    now: Callable[[], datetime],
) -> IndexResult:
    """Embed the document's chunks that lack a current vector. Commits per batch."""
    marker = _job_marker(session, document_id)
    if marker is None or marker[:2] != ("ready", "pending"):
        session.rollback()
        return IndexResult(document_id, "discarded", 0, 0)
    chunks = session.execute(
        select(DocumentChunk.id, DocumentChunk.text, DocumentChunk.content_sha256)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.number)
    ).all()
    current: dict[uuid.UUID, str] = {
        chunk_id: sha
        for chunk_id, sha in session.execute(
            select(DocumentChunkEmbedding.chunk_id, DocumentChunkEmbedding.content_sha256).where(
                DocumentChunkEmbedding.document_id == document_id,
                DocumentChunkEmbedding.model == provider.model,
            )
        )
    }
    todo = [c for c in chunks if current.get(c.id) != c.content_sha256]
    session.commit()

    embedded = 0
    try:
        for start in range(0, len(todo), batch_size):
            batch = todo[start : start + batch_size]
            vectors = provider.embed_passages([c.text for c in batch])
            if len(vectors) != len(batch) or any(len(v) != provider.dimensions for v in vectors):
                raise ValueError("the model returned vectors of the wrong number or size")
            if _job_marker(session, document_id) != marker:
                session.rollback()
                return IndexResult(document_id, "discarded", embedded, len(chunks) - len(todo))
            rows = [
                {
                    "chunk_id": c.id,
                    "model": provider.model,
                    "document_id": document_id,
                    "content_sha256": c.content_sha256,
                    "dimensions": provider.dimensions,
                    "embedding": vector,
                }
                for c, vector in zip(batch, vectors, strict=True)
            ]
            statement = insert(DocumentChunkEmbedding).values(rows)
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=["chunk_id", "model"],
                    set_={
                        "content_sha256": statement.excluded.content_sha256,
                        "embedding": statement.excluded.embedding,
                        "dimensions": statement.excluded.dimensions,
                        "created_at": text("now()"),
                    },
                )
            )
            session.commit()  # partial progress survives a crash
            embedded += len(batch)
    except Exception as exc:
        session.rollback()
        reason = f"Embedding failed: {type(exc).__name__}: {exc}"[:REASON_MAX]
        _finish(session, document_id, marker, "failed", reason, None, None)
        logger.warning("document %s: indexing failed (%s)", document_id, type(exc).__name__)
        return IndexResult(document_id, "failed", embedded, len(chunks) - len(todo))

    session.execute(
        delete(DocumentChunkEmbedding).where(
            DocumentChunkEmbedding.document_id == document_id,
            DocumentChunkEmbedding.model != provider.model,
        )
    )
    if not _finish(session, document_id, marker, "indexed", None, provider.model, now()):
        return IndexResult(document_id, "discarded", embedded, len(chunks) - len(todo))
    logger.info(
        "document %s: indexed (%d chunks embedded, %d already current)",
        document_id,
        embedded,
        len(chunks) - len(todo),
    )
    return IndexResult(document_id, "indexed", embedded, len(chunks) - len(todo))


def _finish(
    session: Session,
    document_id: uuid.UUID,
    marker: tuple[str, str, object],
    status: str,
    reason: str | None,
    model: str | None,
    indexed_at: datetime | None,
) -> bool:
    """Record the outcome only if the job is still the one that was indexed."""
    result = session.execute(
        update(DocumentExtraction)
        .where(
            DocumentExtraction.document_id == document_id,
            DocumentExtraction.status == "ready",
            DocumentExtraction.index_status == "pending",
            DocumentExtraction.finished_at == marker[2],
        )
        .values(
            index_status=status,
            index_reason=reason,
            embedding_model=model,
            indexed_at=indexed_at,
        )
    )
    session.commit()
    return bool(result.rowcount)  # type: ignore[attr-defined]
