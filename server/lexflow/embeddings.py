"""Embeddings for document chunks: the provider interface, and whether it can run.

Embeddings are off by default (``LEXFLOW_EMBEDDINGS=disabled``): chunks are
stored without vectors and their index status is "disabled". The approved
design adds an optional local model (``BAAI/bge-small-en-v1.5``), downloaded
only by an explicit command and never by the worker, with vectors stored in
PostgreSQL through the pgvector extension.

That storage is not set up yet. The database image named in the plan,
``pgvector/pgvector:pg17``, is built on an older C library than the current
``postgres:17`` image, which would change how existing text is sorted and
indexed, so the image was not changed (``docs/PHASE3_EXECUTION_LOG.md``, P3-M5).
Until it is, ``LEXFLOW_EMBEDDINGS=local`` is refused with that reason rather
than accepted and left to do nothing.

Nothing here downloads a model or sends text to another service.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from lexflow.config import Settings

UNAVAILABLE = (
    "LEXFLOW_EMBEDDINGS=local is not available yet: storing embeddings needs a "
    "PostgreSQL image with the pgvector extension, which has not been set up "
    "(see docs/PHASE3_EXECUTION_LOG.md, P3-M5). Set LEXFLOW_EMBEDDINGS=disabled."
)


class EmbeddingsUnavailableError(Exception):
    """The configured embeddings cannot be produced or stored here."""


class EmbeddingProvider(Protocol):
    """Turns chunk texts into vectors, on this computer."""

    model: str
    dimensions: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """One vector per text, in the same order."""
        ...


def provider_for(settings: Settings) -> EmbeddingProvider | None:
    """The provider the settings ask for; ``None`` when embeddings are off.

    Raises ``EmbeddingsUnavailableError`` for a choice this installation cannot
    honour, so the worker refuses to start instead of marking chunks "pending"
    that nothing would ever index.
    """
    if settings.embeddings == "disabled":
        return None
    raise EmbeddingsUnavailableError(UNAVAILABLE)
