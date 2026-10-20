"""Embedding extracted chunks: storage, retries, model changes, concurrency.

Uses committed data (``committed_engine``): indexing takes a per-document
advisory lock on its own connection, which a rolled-back test transaction
could not show. The model is ``WordsProvider`` (test-only, not a language
model); the real model is tested in ``test_embeddings.py``.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import Engine, delete, func, select, text, update
from sqlalchemy.orm import Session, sessionmaker

from lexflow import worker
from lexflow.config import get_settings
from lexflow.models import (
    DocumentChunk,
    DocumentChunkEmbedding,
    DocumentExtraction,
    DocumentSection,
)
from lexflow.seed import sample_uuid
from lexflow.seed.loader import load_sample_data
from lexflow.services import indexing
from lexflow.storage import LocalDiskStorage
from tests.embedding_fakes import NOW, WordsProvider, make_ready

SATTVIK = sample_uuid("case", "case-1005")
PAGES = [
    "FICTIONAL. The tenant stopped paying rent in March. " * 20,
    "FICTIONAL. The landlord served a notice to quit. " * 20,
    "FICTIONAL. The court listed the matter for hearing. " * 20,
]


@pytest.fixture
def engine_with_case(committed_engine: Engine) -> Engine:
    with Session(committed_engine) as session, session.begin():
        load_sample_data(session)
    return committed_engine


def ready(engine: Engine, name: str = "Petition.pdf", **kwargs: object) -> uuid.UUID:
    with Session(engine) as session:
        return make_ready(session, SATTVIK, name, PAGES, **kwargs)  # type: ignore[arg-type]


def job(engine: Engine, document_id: uuid.UUID) -> DocumentExtraction:
    with Session(engine, expire_on_commit=False) as session:
        found = session.get(DocumentExtraction, document_id)
        assert found is not None
        return found


def vectors(engine: Engine, document_id: uuid.UUID, model: str | None = None) -> int:
    with Session(engine) as session:
        query = (
            select(func.count())
            .select_from(DocumentChunkEmbedding)
            .where(DocumentChunkEmbedding.document_id == document_id)
        )
        if model:
            query = query.where(DocumentChunkEmbedding.model == model)
        return int(session.scalar(query) or 0)


def chunk_count(engine: Engine, document_id: uuid.UUID) -> int:
    with Session(engine) as session:
        return int(
            session.scalar(
                select(func.count())
                .select_from(DocumentChunk)
                .where(DocumentChunk.document_id == document_id)
            )
            or 0
        )


def index(engine: Engine, provider: WordsProvider, batch_size: int = 2) -> object:
    return indexing.index_next(engine, provider, batch_size=batch_size, now=lambda: NOW)


def requeue(engine: Engine, document_id: uuid.UUID) -> None:
    with Session(engine) as session, session.begin():
        session.execute(
            update(DocumentExtraction)
            .where(DocumentExtraction.document_id == document_id)
            .values(index_status="pending", index_reason=None)
        )


def test_a_waiting_document_gets_one_vector_per_chunk(engine_with_case: Engine) -> None:
    document = ready(engine_with_case)
    provider = WordsProvider()
    result = index(engine_with_case, provider)
    assert result == indexing.IndexResult(
        document, "indexed", chunk_count(engine_with_case, document), 0
    )
    done = job(engine_with_case, document)
    assert (done.index_status, done.embedding_model, done.index_reason) == (
        "indexed",
        provider.model,
        None,
    )
    assert done.indexed_at == NOW
    assert vectors(engine_with_case, document) == chunk_count(engine_with_case, document)
    with Session(engine_with_case) as session:
        row = session.scalars(select(DocumentChunkEmbedding).limit(1)).one()
        chunk = session.get(DocumentChunk, row.chunk_id)
        assert chunk is not None
        assert row.content_sha256 == chunk.content_sha256 and row.dimensions == 384
        assert len(row.embedding) == 384
    assert index(engine_with_case, provider) is None  # nothing else waiting


def test_indexing_again_embeds_nothing_twice(engine_with_case: Engine) -> None:
    document = ready(engine_with_case)
    provider = WordsProvider()
    index(engine_with_case, provider)
    embedded = len(provider.embedded)
    requeue(engine_with_case, document)
    result = index(engine_with_case, provider)
    assert isinstance(result, indexing.IndexResult)
    assert (result.status, result.embedded) == ("indexed", 0)
    assert result.reused == chunk_count(engine_with_case, document)
    assert len(provider.embedded) == embedded


def test_a_failure_keeps_finished_batches_and_a_retry_completes(engine_with_case: Engine) -> None:
    document = ready(engine_with_case)
    total = chunk_count(engine_with_case, document)
    assert total > 2
    broken = WordsProvider(fail_on_call=2)  # the second batch fails
    result = index(engine_with_case, broken, batch_size=2)
    assert isinstance(result, indexing.IndexResult) and result.status == "failed"
    failed = job(engine_with_case, document)
    assert failed.index_status == "failed"
    assert failed.index_reason and "failed on purpose" in failed.index_reason
    assert vectors(engine_with_case, document) == 2  # the first batch was committed
    assert index(engine_with_case, WordsProvider()) is None  # not retried by itself

    requeue(engine_with_case, document)
    retry = WordsProvider()
    result = index(engine_with_case, retry, batch_size=2)
    assert isinstance(result, indexing.IndexResult)
    assert (result.status, result.embedded, result.reused) == ("indexed", total - 2, 2)
    assert vectors(engine_with_case, document) == total


def test_a_changed_chunk_is_embedded_again(engine_with_case: Engine) -> None:
    document = ready(engine_with_case)
    provider = WordsProvider()
    index(engine_with_case, provider)
    with Session(engine_with_case) as session, session.begin():
        chunk = session.scalars(
            select(DocumentChunk).where(DocumentChunk.document_id == document).limit(1)
        ).one()
        chunk.content_sha256 = "f" * 64  # as if its text had changed
        chunk_id = chunk.id
    requeue(engine_with_case, document)
    again = WordsProvider()
    result = index(engine_with_case, again)
    assert isinstance(result, indexing.IndexResult) and result.embedded == 1
    with Session(engine_with_case) as session:
        stored = session.scalar(
            select(DocumentChunkEmbedding.content_sha256).where(
                DocumentChunkEmbedding.chunk_id == chunk_id
            )
        )
    assert stored == "f" * 64


def test_a_new_model_replaces_the_old_vectors(engine_with_case: Engine) -> None:
    document = ready(engine_with_case)
    index(engine_with_case, WordsProvider("old-model@1"))
    requeue(engine_with_case, document)
    index(engine_with_case, WordsProvider("new-model@2"))
    total = chunk_count(engine_with_case, document)
    assert vectors(engine_with_case, document, "new-model@2") == total
    assert vectors(engine_with_case, document, "old-model@1") == 0
    assert job(engine_with_case, document).embedding_model == "new-model@2"


def test_extracting_again_removes_the_vectors_with_the_old_text(engine_with_case: Engine) -> None:
    document = ready(engine_with_case)
    index(engine_with_case, WordsProvider())
    assert vectors(engine_with_case, document) > 0
    with Session(engine_with_case) as session, session.begin():
        session.execute(delete(DocumentSection).where(DocumentSection.document_id == document))
    assert vectors(engine_with_case, document) == 0  # chunks cascade, vectors cascade


def test_text_extracted_again_during_indexing_discards_the_result(
    engine_with_case: Engine,
) -> None:
    document = ready(engine_with_case)

    class Interrupting(WordsProvider):
        def embed_passages(self, texts: object) -> list[list[float]]:
            with Session(engine_with_case) as other, other.begin():
                other.execute(
                    update(DocumentExtraction)
                    .where(DocumentExtraction.document_id == document)
                    .values(status="queued", index_status="disabled")
                )
            return super().embed_passages(texts)  # type: ignore[arg-type]

    result = index(engine_with_case, Interrupting())
    assert isinstance(result, indexing.IndexResult) and result.status == "discarded"
    assert job(engine_with_case, document).index_status == "disabled"
    assert vectors(engine_with_case, document) == 0


def test_a_document_locked_by_another_worker_is_skipped(engine_with_case: Engine) -> None:
    document = ready(engine_with_case)
    with engine_with_case.connect() as other:
        key = other.scalar(text(indexing.LOCK_KEY), {"id": str(document)})
        assert other.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": key})
        assert index(engine_with_case, WordsProvider()) is None
        other.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})
        other.commit()
    assert job(engine_with_case, document).index_status == "pending"
    result = index(engine_with_case, WordsProvider())
    assert isinstance(result, indexing.IndexResult) and result.status == "indexed"


def test_only_ready_documents_waiting_for_indexing_are_taken(engine_with_case: Engine) -> None:
    disabled = ready(engine_with_case, "Off.pdf", index_status="disabled")
    assert index(engine_with_case, WordsProvider()) is None
    assert vectors(engine_with_case, disabled) == 0


@contextmanager
def _sessions(engine: Engine) -> Iterator[Session]:
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        yield session


def test_the_worker_queues_extracted_text_for_indexing_and_indexes_it(
    engine_with_case: Engine, tmp_path: object
) -> None:
    from lexflow.extraction import Extracted, Section

    with Session(engine_with_case) as session:
        document = make_ready(session, SATTVIK, "Waiting.pdf", PAGES)
        # Put it back in the queue, as a fresh upload would be.
        session.execute(
            update(DocumentExtraction)
            .where(DocumentExtraction.document_id == document)
            .values(status="queued", index_status="disabled", finished_at=None)
        )
        session.commit()

    def extract(*_: object) -> Extracted:
        return Extracted([Section(1, PAGES[0])], extractor="test", page_count=1)

    def read(*_: object) -> bytes:
        return b"%PDF"

    provider = WordsProvider()
    original = worker._read
    worker._read = read  # type: ignore[assignment]
    try:
        processed = worker.run(
            lambda: _sessions(engine_with_case),
            LocalDiskStorage(tmp_path),  # type: ignore[arg-type]
            get_settings(),
            worker_id="test",
            once=True,
            extract=extract,
            engine=engine_with_case,
            provider=provider,
        )
    finally:
        worker._read = original
    assert processed == 2  # the extraction, then the indexing
    done = job(engine_with_case, document)
    assert (done.status, done.index_status, done.embedding_model) == (
        "ready",
        "indexed",
        provider.model,
    )
    assert vectors(engine_with_case, document) == chunk_count(engine_with_case, document)


def test_without_embeddings_the_worker_indexes_nothing(engine_with_case: Engine) -> None:
    document = ready(engine_with_case)  # waiting, but embeddings are off
    processed = worker.run(
        lambda: _sessions(engine_with_case),
        LocalDiskStorage(get_settings().upload_dir),
        get_settings(),
        worker_id="test",
        once=True,
        engine=engine_with_case,
        provider=None,
    )
    assert processed == 0
    assert job(engine_with_case, document).index_status == "pending"
    assert vectors(engine_with_case, document) == 0
