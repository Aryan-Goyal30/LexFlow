# Embeddings execution log (pgvector, local model, semantic retrieval)

Implements the embeddings part of Phase 3 that was blocked in P3-M5
(`docs/PHASE3_EXECUTION_LOG.md`, ADR 0016). Started 2026-10-20.

## How to resume (read this first)

1. `git log --oneline` — milestone commits start with `Embeddings E<n>`.
2. Read the **Checkpoint** line at the end of this file.
3. Scratch resources are listed under "Scratch resources"; their passwords
   live only in the session scratchpad, never in the repository.
4. Unattended resumption is **not available** in this environment
   (`ScheduleWakeup` works only inside `/loop`); checkpoints are the recovery
   mechanism.

## Start state (verified 2026-10-20)

- Branch `master`, HEAD `ffb775b`, working tree clean, no remote.
- `docs/DEVELOPMENT_BRIEF.md` SHA-256 starts `274ecaed93400f51` (unchanged).
- Live database: `server/.env` → 127.0.0.1:5432 `lexflow`; container
  `lexflow-db-1` (from `server/compose.yaml`), image `postgres:17`
  (`sha256:2d2b8998d310…`), volume `lexflow_pgdata`; revision **0008**.
  Since Phase 3 the owner extracted one document (1 job, 1 section, 2 chunks).
- Earlier backups verified: Phase 2 `a23f85a0…870d`, Phase 3 `2b058840…a22e`.
- Python 3.12.3; no numpy/onnxruntime/tokenizers installed. Machine: 32 logical
  CPUs, 15.2 GB RAM, no GPU used.

## E1 — Backup and isolated compatibility (done)

**Fresh backups (git-ignored, `server/var/backups/`):**

| Backup | SHA-256 | Notes |
|---|---|---|
| `lexflow-20261020-pre-pgvector.dump` (logical, `pg_dump -Fc`) | `9e5f114ab0fa8e5c42962d1d73dd97043aa9028319ce672d30a12a1727378bfa` | same inside/outside the container; 14 table-data entries |
| `lexflow-20261020-pre-pgvector-basebackup/` (physical, `pg_basebackup -Ft -z -X stream -c fast`) | base `92c4e0a2…c181`, wal `7eed03e0…b4fb7` | whole cluster (all databases); read-only on the source |

**Physical rehearsal (the real image swap, isolated):** the base backup was
unpacked into a new volume `lexflow_pgv_physical_scratch` and started with
`pgvector/pgvector:pg17-trixie` (`sha256:7a7e9f22015b…`, PostgreSQL
17.11-1.pgdg13+2, glibc 2.41-12+deb13u4, pgvector 0.8.7) as container
`lexflow-pgv-physical` (no published port). Results:
- backup recovery completed, consistent state reached, no warnings;
- collation recorded = actual = **2.41** in all 7 databases;
- `amcheck` `bt_index_check(heapallindexed)` passed on **every B-tree index**
  of every database (1,032 indexes);
- `lexflow` fingerprint (count + md5 of every row, every table) identical to
  the live database;
- pgvector: `CREATE EXTENSION vector` 0.8.7; insert/update of 2,003
  `vector(384)` rows; exact cosine ranking correct; HNSW index built and used
  by the planner (`Index Scan using … Order By <=>`); `REINDEX` ok;
  wrong-dimension insert refused; no server warnings.

**Logical rehearsal:** throwaway server `lexflow-pgv-test`
(`pg17-trixie`, tmpfs, 127.0.0.1:55432, random password in the scratchpad)
— the logical backup restored with `--exit-on-error` into
`lexflow_pgv_restore`; fingerprint identical to live; collation 2.41/2.41.

`pgvector/pgvector:pg17` (Debian 12, glibc 2.36) remains **rejected**.

## Library choice

`onnxruntime` + `tokenizers` + `numpy`, with a standard-library downloader:
- the model repository `BAAI/bge-small-en-v1.5` (MIT) ships an official ONNX
  export; files are pinned to revision
  `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a` and verified by SHA-256
  (`onnx/model.onnx` `828e1496…cf35`, 133,093,490 bytes);
- loading is from local files only, so the worker cannot download anything;
- CLS pooling and L2 normalisation (from `1_Pooling/config.json`), max 512
  tokens, lower-cased WordPiece; queries get the model's retrieval
  instruction, passages do not;
- rejected: `fastembed` (more dependencies, defaults to a third-party
  quantised re-export, its own download behaviour) and
  `sentence-transformers` (PyTorch, ~2 GB).

## Scratch resources (created by this work; keep until the work is accepted)

| Resource | Kind | Purpose |
|---|---|---|
| `lexflow-pgv-physical` | container (stopped when not needed) | physical copy under `pg17-trixie` |
| `lexflow_pgv_physical_scratch` | volume | that copy's data |
| `lexflow-pgv-test` | container, tmpfs, 127.0.0.1:55432 | isolated test server and logical restore |

## E2 — Storage, provider, worker, retrieval (done)

**Baseline on the candidate image:** the existing back-end suite against the
scratch `pg17-trixie` server (`TEST_DATABASE_URL` → 127.0.0.1:55432
`lexflow_test`): **589 passed** — the application works unchanged on it.

**Migration 0009** (`server/migrations/versions/0009_chunk_embeddings.py`):
`CREATE EXTENSION IF NOT EXISTS vector` and one new table
`document_chunk_embeddings` — `(chunk_id, model)` primary key; `chunk_id` →
`document_chunks` and `document_id` → `documents`, both `ON DELETE CASCADE`;
`content_sha256` (the chunk's hash when embedded), `dimensions` (checked equal
to `vector_dims(embedding)`), `embedding vector(384)`, `created_at`; index
`(document_id, model)`. No existing table changes. No approximate (HNSW)
index: searches are per case with an exact cosine distance (a filtered HNSW
search can silently miss rows; per-case sets are small).
Rehearsal on the scratch restore `lexflow_pgv_restore` (script refuses any
other database): upgrade 0009 → existing 13 tables identical, new table empty,
extension present; downgrade 0008 → whole database identical, extension gone;
upgrade 0009 again → identical. **PASSED.**

**Dependencies** (pinned with pip-compile; no existing pin changed):
`onnxruntime 1.31.0`, `tokenizers 0.23.3`, `numpy 2.5.4`, `pgvector 0.5.1`
(+ transitive `huggingface-hub`, `protobuf`, …; `httpx2`/`httpcore2` kept at the
dev set's 2.14.0). onnxruntime reports CPU and Azure execution providers; the
provider pins `CPUExecutionProvider` only.

**Code:**
- `lexflow/embeddings.py`: pinned manifest (revision + SHA-256 + size per
  file), `check_files`, `LocalBgeProvider` (local files only; tokenizer
  truncation 512; CLS pooling; L2 normalisation; output shape and finiteness
  checked; batches; `LEXFLOW_EMBEDDING_THREADS`), `provider_for` (disabled →
  none; missing/damaged files or another model → `EmbeddingsUnavailableError`
  with the download command), `check_database` (migration 0009 present).
  Model key stored with vectors: `BAAI/bge-small-en-v1.5@5c38ec7c405e`.
- `lexflow/services/indexing.py`: `index_next` (per-document session advisory
  lock), `index_document` (embeds only chunks without a current vector, commits
  per batch, discards if the text was re-extracted meanwhile, records
  `indexed`/`failed` with reason, removes other models' vectors on success).
- `lexflow/worker.py`: with embeddings on, refuses to start unless the model
  and table are ready; extracted text is stored with `index_status=pending`;
  waiting documents are indexed whenever no extraction is waiting. Off (the
  default): unchanged behaviour.
- `lexflow/cli/models.py`: `status`, `download` (preview; `--confirm` streams
  each file to `.part`, checks size + SHA-256, then renames; audited
  `model.downloaded`), `verify`, `queue-indexing` (preview; `--confirm N`;
  audited `document.indexing_queued`).
- `lexflow/services/retrieval.py` + `lexflow/api/search.py`:
  `GET /api/cases/{id}/search?q=&mode=keyword|semantic|hybrid&limit=` — staff
  router + `authz.load_case(VIEW)`; live documents with ready text only;
  semantic needs a vector of the current model and the chunk's current hash;
  results carry document, chunk, section, page, exact offsets; audited
  `case.searched` with mode/results/limit (never the query). 409
  `semantic-search-unavailable` with the reason when embeddings cannot run.
  No UI (not a legal-research feature yet).
- CI services switched to `pgvector/pgvector:pg17-trixie` (migration 0009
  needs pgvector). `server/compose.yaml` (the live database) is unchanged.

**Intermittent test finally explained.** `test_auth_committed.py::
test_failures_and_lockout_survive_the_failed_requests` failed again in a full
run; the saved output showed all five audit events present but
`events[-1].details["locked"] is False`: the query had **no ORDER BY**, so the
row order was arbitrary. Not an application bug and not lost audit rows (the
earlier hypothesis was wrong). Fixed by ordering by `occurred_at, id` and
asserting `locked` is false for the first four and true for the fifth; passed
8 consecutive runs and the full suites since.

**Tests (all on the scratch pgvector server):** new `test_indexing.py` (11),
`test_search.py` (18), `test_embeddings.py` rewritten (20 + 4 that need the
real model and are skipped until it is downloaded). Full suite **624 passed,
4 skipped**. ruff, format, mypy (Windows and `--platform linux`, 117 files)
clean. `npm run check`: 158 tests, API types match, build OK.

E2 commits: `35f888d` (implementation), `8eda562` (a test the first mutation
run showed was missing: vectors of another model are never compared).

## E3 — Mutation checks, model download, evaluation (done)

**Mutation checks** (`docs/verification/embeddings/run_mutation_checks.py`,
report `mutation-report.md`, raw `mutation-output.log`, redacted): 16 guards
in search, indexing, the worker and the model CLI. First run 15/16 — S-4
(model filter in semantic search) survived; a test was added (`8eda562`).
Second run **16/16 caught**, all by test assertions (no import/collection
errors), every file restored byte-for-byte.

**Model download** — only through the explicit command:
`python -m lexflow.cli.models download` (preview: 4 files, 133.8 MB, nothing
created) then `--confirm`: each file streamed to `.part`, size and SHA-256
checked, renamed; ~80 s. Stored in `server/var/models/BAAI/bge-small-en-v1.5/
5c38ec7c…/` (git-ignored, never committed). Audited `model.downloaded` in
`lexflow` (one audit row; no schema change). `verify`: loaded in 0.6 s;
384 dimensions; unit length; related pair 0.715 vs unrelated 0.554. CPU only
(no GPU used or claimed).

**Real-model tests:** the 4 previously skipped tests pass (unit 384-d
vectors including empty and over-long text; deterministic and
batch-independent to 1e-4; related meaning closer; query instruction
applied). Full back-end suite on the scratch pgvector server with the model
present: **629 passed, 0 skipped** (`pytest-full-scratch-pgvector.log`).

**Evaluation** (`server/scripts/evaluate_retrieval.py`, results
`retrieval-eval.md`/`.json`): FICTIONAL corpus of 8 documents / 18 pages,
26 queries each with exactly one answering page (12 lexical, 14 paraphrase),
written by the developer — measures plumbing and gross behaviour, not legal
research quality. Throwaway database `lexflow_eval_test` on the scratch
server, dropped afterwards. Indexing took 0.30 s.

| Queries | Mode | Recall@1 | Recall@3 | Recall@5 | MRR@10 |
|---|---|---|---|---|---|
| all (26) | keyword | 0.385 | 0.385 | 0.385 | 0.385 |
| all (26) | semantic | 0.885 | 1.0 | 1.0 | 0.936 |
| all (26) | hybrid | 0.885 | 1.0 | 1.0 | 0.936 |
| lexical (12) | keyword | 0.833 | 0.833 | 0.833 | 0.833 |
| lexical (12) | semantic | 1.0 | 1.0 | 1.0 | 1.0 |
| paraphrase (14) | keyword | 0.0 | 0.0 | 0.0 | 0.0 |
| paraphrase (14) | semantic | 0.786 | 1.0 | 1.0 | 0.881 |

Reading: keyword search (`websearch_to_tsquery`) requires every term, so it
finds nothing when the wording differs and misses 2 lexical queries with one
absent word. Semantic search ranked the answering page in the top 3 for all
26 queries and first for 23. Hybrid equals semantic here because keyword
adds almost nothing on this corpus. With 26 hand-written queries these are
indications, not benchmarks; a lawyer-reviewed relevance set on real
(licensed) material is needed for any claim about legal research.

---

Checkpoint: E3 committed (see `git log`). Next: E4 gated live change —
fresh backups, physical rehearsal of 0009 and of the rollback, image swap of
`lexflow-db-1` to `pgvector/pgvector:pg17-trixie`, migration 0009, checks.
