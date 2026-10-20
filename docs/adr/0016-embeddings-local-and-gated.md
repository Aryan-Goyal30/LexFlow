# 0016 — Embeddings: off by default, local only, and gated on a compatible pgvector image

Status: Superseded in part by 0017 (the image was approved and applied; storage and the
local model are implemented). Kept for the compatibility analysis.

## Context

Retrieval in later phases needs vector embeddings of document chunks. Client
documents are confidential, so text must not leave the machine unless the
owner configures it. The brief recommends PostgreSQL with pgvector. The
current database image (`postgres:17`, Debian 13, glibc 2.41) has no pgvector,
and the existing development database must be preserved.

## Decision

- **Disabled by default** (`LEXFLOW_EMBEDDINGS=disabled`). Chunks are stored
  with index status `disabled`; nothing pretends to be indexed.
- **Behind an interface** (`lexflow/embeddings.py`, `EmbeddingProvider`). The
  only planned provider is **local**: `BAAI/bge-small-en-v1.5` (384
  dimensions), downloaded **only** by an explicit operator command, never by
  the worker or the API. No hosted embedding service.
- **Storage in pgvector** (`vector(384)` per chunk, with the model name), once
  the database image provides it.
- **Image compatibility first.** The planned `pgvector/pgvector:pg17` image is
  built on Debian 12 (glibc 2.36). The existing cluster's `en_US.utf8`
  collations were created under glibc 2.41; running the data directory on the
  older C library risks wrongly ordered text indexes. So it was **not**
  applied. `pgvector/pgvector:pg17-trixie` matches the current image exactly
  (PostgreSQL 17.11-1.pgdg13+2, glibc 2.41-12+deb13u4, pgvector 0.8.7), and a
  restore of the development backup on it passed, but it is a different tag
  from the one approved and awaits the owner's decision.
- **Until then, `local` is refused** with the reason (the worker will not
  start, rather than mark chunks "pending" that nothing would index), and
  `python -m lexflow.cli.models status` reports the setup read-only.

## Consequences

- Phase 3's "compute embeddings; store in pgvector" is not done. Text,
  sections and chunks are, so embeddings can be computed later from stored
  chunks without re-extracting.
- Switching the image must follow the database safety procedure (backup,
  restore check, fingerprints, rehearsal) and update `compose.yaml` and CI
  together, so tests and development use the same image.
- A multilingual model (for Hindi and other Indian languages) can be added
  later behind the same interface; vectors from different models are never
  mixed (the model name is stored with each).
