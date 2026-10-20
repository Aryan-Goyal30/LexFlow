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

E3 commit: `4c6dc96`.

## E4 — Gated live change (done)

**Rehearsals on the physical copy** (the real data directory, isolated):
the exact SQL of `alembic upgrade 0008:0009 --sql` → existing tables
identical; the downgrade SQL → whole database identical, `vector` removed;
then the candidate container was stopped and **`postgres:17` started on the
same data** (`lexflow-pgv-rollback`): started cleanly, collation 2.41/2.41,
`amcheck` passed on all 1,032 B-tree indexes in 7 databases, data identical.
So both directions and the image rollback are rehearsed.

**Gates (all passed before the change):** fresh checksummed backups ✔;
logical and physical restores ✔; candidate compatibility (collation, amcheck,
pgvector operations) ✔; 0009 upgrade/downgrade/re-upgrade on the logical
restore and the physical copy ✔; rollback rehearsed ✔; automated tests
(629 passed on the candidate image) ✔; live target identified ✔.

**Pre-change record:** container `165f4f29ea25…` (`postgres:17`,
`sha256:2d2b8998d310…`), volume `lexflow_pgdata`, compose project `lexflow`,
revision 0008, no client connections (the dev API and worker were stopped).

**Backups taken immediately before** (`server/var/backups/`, git-ignored):

| Backup | SHA-256 |
|---|---|
| `lexflow-20261020-pre-swap.dump` (logical, 14 table-data entries) | `8a433f2e7328dca506e1dd99806168ce3e00fa8a7e2270d9dc8e1e39d5b1567a` |
| `lexflow-20261020-pre-swap-basebackup/base.tar.gz` (physical) | `f21638c6171517d30f4b0a8858021cfe69634d7e8e70c16248b361847e6a92b5` |
| `lexflow-20261020-pre-swap-basebackup/pg_wal.tar.gz` | `6cf7c0e81db3b7d3ec26c74e7b4c785bf1e400f17e6960e0ff263dc6601ae016` |
| volume `lexflow_pgdata_pre_pgvector_20261020` (cold copy while stopped) | 2,837 files, 118,683,330 bytes, per-file hash list `d743079ad14c5f0e…` identical to the source |

**Change (the rehearsed procedure):** `docker compose stop db`; cold volume
copy; `compose.yaml` `image: pgvector/pgvector:pg17-trixie`;
`docker compose up -d --wait db` → new container `e7908aef99c9…`, same
volume, "Skipping initialization", clean start, healthy. Checks: collation
2.41/2.41 in all 7 databases; `lexflow` fingerprint identical to the pre-swap
one; `vector` 0.8.7 available; port still 127.0.0.1 only; no warnings.
Then `alembic upgrade head` on `lexflow` → **0009 (head)**; existing 13
tables identical; new table empty; extensions `plpgsql`, `vector 0.8.7`;
`alembic check` clean.

**After the change:**
- API restarted (health ok; anonymous search/text 401; route in OpenAPI);
  worker restarted with embeddings **disabled** (the default).
- `models status` on `lexflow`: model verified, pgvector installed, 1
  extracted document (index status `disabled`), 0 vectors.
- Full back-end suite with the **default** test configuration (now the live
  cluster's `lexflow_test`): **629 passed**
  (`docs/verification/embeddings/pytest-full-live-cluster.log`).
- Playwright on the live cluster's `lexflow_e2e`: **32 passed**
  (`playwright-live-cluster.log`); no leftover processes.
- Real worker + real model on the live server, FICTIONAL e2e data only
  (`live_worker_smoke.py`, `live-worker-smoke.log`): `queue-indexing`
  preview + `--confirm 5`; `python -m lexflow.worker --once` with
  `LEXFLOW_EMBEDDINGS=local` indexed 5 documents (7 chunks); every document
  has one vector per chunk from the pinned model; a semantic search returned
  passages whose offsets match the stored text; deleted documents excluded.
  **PASSED.**
- `lexflow` fingerprint after all of this: unchanged since migration 0009.

**Not done on purpose:** embeddings were **not enabled** for `lexflow` and
the owner's extracted document was **not** indexed — enabling is a
configuration decision for the owner (`server/README.md`, "Embeddings and
case search").

**Recovery (rehearsed):** (1) `alembic downgrade 0008`; (2) then
`docker compose stop db`, `image: postgres:17`, `docker compose up -d --wait
db`; (3) if anything else fails: the cold volume copy, the physical base
backup or the logical dump above (restoring replaces data: owner decision).

## Scratch resources (left in place; remove only when the owner agrees)

| Resource | State | Notes |
|---|---|---|
| `lexflow_pgdata_pre_pgvector_20261020` | volume | **the pre-change snapshot; keep until satisfied** |
| `lexflow-pgv-test` | container, running, tmpfs, 127.0.0.1:55432 | scratch test server; its data vanishes when stopped |
| `lexflow-pgv-physical`, `lexflow-pgv-rollback` | containers, stopped | rehearsal servers |
| `lexflow_pgv_physical_scratch` | volume | the physical rehearsal copy |
| `lexflow-pgvector-rehearsal` | container, stopped | from Phase 3 |
| `lexflow_p3_restore`, `lexflow_restore_check` | databases in the live cluster | earlier restore checks |

## Final state

- Live: `pgvector/pgvector:pg17-trixie`, volume `lexflow_pgdata`, `lexflow`
  at **0009**; embeddings **disabled**; model downloaded and verified;
  API and worker running.
- Tests: back end 629 passed (scratch and live cluster); Playwright 32;
  front end 158 + build; mutation checks 16/16; evaluation recorded.

---

Checkpoint: E4 committed (see `git log`). Embeddings implemented and the live
database migrated. Next actions are the owner's: enable embeddings if wanted
(`LEXFLOW_EMBEDDINGS=local`, restart, `queue-indexing`), keep or remove the
scratch resources, decide on a search screen and on Phase 4.
