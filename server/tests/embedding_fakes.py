"""Test-only stand-ins for the embedding model and helpers to make indexed documents.

``WordsProvider`` is NOT a language model: it hashes each word into one of 384
dimensions, so texts that share words get similar vectors. That is enough to
test storage, ranking plumbing, retries and access rules without the real
model. Tests of the real model live in ``test_embeddings.py`` and need it
downloaded.
"""

from __future__ import annotations

import hashlib
import math
import re
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from lexflow.extraction import Section
from lexflow.extraction.chunking import chunk_sections
from lexflow.models import Document
from lexflow.services import extraction_queue as queue

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


class WordsProvider:
    """Deterministic bag-of-words vectors; counts calls; can fail on a chosen call."""

    dimensions = 384

    def __init__(self, model: str = "test-words@1", *, fail_on_call: int | None = None) -> None:
        self.model = model
        self.fail_on_call = fail_on_call
        self.calls = 0
        self.embedded: list[str] = []

    def vector(self, text: str) -> list[float]:
        values = [0.0] * self.dimensions
        for word in re.findall(r"[a-z]+", text.lower()):
            values[int(hashlib.sha256(word.encode()).hexdigest(), 16) % self.dimensions] += 1.0
        norm = math.sqrt(sum(v * v for v in values))
        if norm == 0:
            values[0], norm = 1.0, 1.0
        return [v / norm for v in values]

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls += 1
        if self.fail_on_call == self.calls:
            raise RuntimeError("the test model failed on purpose")
        self.embedded.extend(texts)
        return [self.vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self.vector(text)


def make_ready(
    session: Session,
    case_id: uuid.UUID,
    name: str,
    pages: Sequence[str | None] | Sequence[str],
    *,
    index_status: str = "pending",
    chunk_size: int = 1200,
) -> uuid.UUID:
    """A stored PDF whose text is extracted (through the real queue functions)."""
    document = Document(
        case_id=case_id,
        name=name,
        document_type="PDF",
        content_type="application/pdf",
        size_bytes=100,
        # Distinct per document, as for real files (the same content twice on one
        # case is refused on upload and restore).
        sha256=hashlib.sha256(f"{name}\n{pages!r}".encode()).hexdigest(),
        storage_key=uuid.uuid4().hex,
        uploaded_on=NOW.date(),
    )
    session.add(document)
    session.flush()
    queue.queue(session, document, requested_by=None, now=NOW)
    session.commit()
    claimed = queue.claim(session, worker_id="test", now=NOW, lease_seconds=300, max_attempts=3)
    assert claimed == document.id
    sections = [Section(number, text or "") for number, text in enumerate(pages, start=1)]
    queue.complete(
        session,
        document.id,
        worker_id="test",
        outcome=queue.Success(
            sections=sections,
            chunks=chunk_sections(sections, chunk_size, min(200, chunk_size // 4)),
            extractor="test",
            page_count=len(sections),
        ),
        now=NOW,
        max_attempts=3,
        index_status=index_status,
    )
    return document.id
