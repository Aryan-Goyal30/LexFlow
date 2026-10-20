# 0017 — pgvector on Debian 13, local embeddings and per-case search

Status: Accepted (2026-10-20). Supersedes the "blocked" parts of 0016.

## Context

ADR 0016 kept embeddings off because the planned image
`pgvector/pgvector:pg17` is built on Debian 12 (glibc 2.36) while the
existing cluster's `en_US.utf8` collations were created under glibc 2.41.
The owner then authorised the compatible candidate
`pgvector/pgvector:pg17-trixie`, subject to backup, restore, compatibility
and migration gates, and asked for the embeddings to be completed.

## Decision

- **Database image `pgvector/pgvector:pg17-trixie`** for development
  (`server/compose.yaml`) and CI: PostgreSQL 17.11-1.pgdg13+2, glibc
  2.41-12+deb13u4, pgvector 0.8.7 — identical to `postgres:17` apart from
  pgvector. Applied only after: fresh logical and physical backups; the
  physical copy started under the new image with collation versions equal
  and `amcheck` passing on every B-tree index; pgvector exercised; migration
  0009 rehearsed both ways; the rollback to `postgres:17` rehearsed on the
  same data; the full test suites passing on the new image.
- **Storage:** `document_chunk_embeddings` (migration 0009), one
  `vector(384)` per chunk and model, with the chunk's SHA-256 when embedded;
  removed with the chunk. Model and hash are both matched at search time, so
  stale or foreign vectors are never compared.
- **Model:** `BAAI/bge-small-en-v1.5` (MIT), official ONNX export, revision
  and files pinned by SHA-256; onnxruntime on the CPU with the model's own
  tokenizer, CLS pooling and L2 normalisation; the model's query instruction
  for queries. Libraries: `onnxruntime`, `tokenizers`, `numpy`, `pgvector`
  (not `fastembed` or `sentence-transformers`: fewer dependencies, no hidden
  downloads, no PyTorch). Downloaded only by
  `python -m lexflow.cli.models download --confirm`; never by the worker or
  API.
- **Off by default.** `LEXFLOW_EMBEDDINGS=local` must be set explicitly; the
  worker refuses to start with it unless the files are intact and migration
  0009 is applied.
- **Indexing in the worker:** after extraction, under a per-document
  advisory lock, only chunks without a current vector, committed per batch;
  failures recorded on the job and retried only on request
  (`queue-indexing`).
- **Search per case, exact.** `GET /api/cases/{id}/search` (keyword,
  semantic, hybrid by reciprocal-rank fusion) for staff who may view the
  case, over its live documents with ready text; exact cosine distance, no
  HNSW index (a filtered approximate search can miss rows; per-case sets are
  small). Audited without the query. No UI yet.

## Consequences

- The development database container was recreated on the new image (same
  volume). Rollback is documented and was rehearsed (`server/README.md`).
- Any new installation needs the pgvector image; plain `postgres:17` can no
  longer run migration 0009.
- English-only model; Hindi and other Indian languages need a multilingual
  model later (vectors are keyed by model, so they can coexist).
- Cross-case or collection-wide search (Phase 4 judgments) will need an
  approximate index and its own evaluation.
- Search quality has been measured only on a small fictional corpus written by
  the developer; legal research quality is unmeasured.
