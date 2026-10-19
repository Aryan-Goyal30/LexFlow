# Phase 3 execution log — Document intelligence

Phase 3 of `docs/DEVELOPMENT_BRIEF.md` ("Document text extraction"): on upload,
a background job extracts text (PDF, DOCX, TXT); each document has a processing
status; text is split into page-aware chunks with embeddings stored in
pgvector; the lawyer can view the extracted text. Nothing is faked: no sample,
canned or simulated text or model output appears in the product.

## How to resume (read this first)

1. `git log --oneline` — each finished milestone is a local commit whose
   message starts with `Phase 3 M<n>`. The **Checkpoint** line at the end of
   this file names the last verified one and the next action.
2. `git status` — uncommitted changes belong to the milestone in progress;
   inspect them before continuing (do not discard them).
3. Re-verify instead of assuming: the database revision
   (`server\.venv\Scripts\python -m alembic current` in `server/`), running
   processes (ports 8000, 5173; any `lexflow.worker`), and the tests of the
   milestone in progress.
4. Never reset or recreate the `lexflow` database or its Docker volume
   (`lexflow_pgdata`). Migrations reach `lexflow` only through the gate
   described under "Database safety".

Resume prompt for a new session:

> Continue LexFlow Phase 3 from the last checkpoint in
> `docs/PHASE3_EXECUTION_LOG.md`. Inspect `git log`, `git status`, the database
> revision and running processes first; do not repeat completed milestones;
> keep every safety rule in that log.

## Approved decisions (owner, 2026-10-20)

- Separate, database-backed worker process (`python -m lexflow.worker`).
- Statuses: `queued`, `processing`, `ready`, `failed`, `unsupported`.
- Bounded extraction for PDF, DOCX and TXT. DOCX (and TXT) page numbers stay
  null; their text is split into numbered *parts* for viewing.
- Page-aware text, chunk metadata, character offsets and content hashes.
- Text viewer, retry, processing status, audit events. No extracted text or
  embeddings for Client accounts.
- Limits (configurable): 1,000 pages, 120 s, 5 MB of extracted text, chunks of
  1,200 characters with about 200 overlapping.
- Embeddings disabled by default; provider interface; optional local
  `BAAI/bge-small-en-v1.5` (384 dimensions), downloaded only by an explicit
  command, never by the worker; multilingual models possible later.
- `pgvector/pgvector:pg17` only after compatibility checks and the database
  safety procedure.
- No Phase 4 or 5 functionality.

## Database safety

`lexflow` (container `lexflow-db-1`, volume `lexflow_pgdata`) is never reset,
recreated or deleted. Before any migration reaches it: verify the target, take a
fresh timestamped backup (git-ignored, `server/var/backups/`), check its SHA-256,
restore it into a scratch database, compare fingerprints, rehearse the migration
there, and prove existing records are preserved. If any check fails: stop before
touching `lexflow`, record the blocker here, continue with independent work.
Tests only recreate `lexflow_test` / `lexflow_e2e` (and the migration-test
scratch database) through the existing test-scoped mechanisms, whose names are
checked before use.

## Start state (inspected 2026-10-20)

- Branch `master`; Phase 2/2b work committed locally as `9f4dfff` (accepted by
  the owner; working tree verified to contain only that work). No remote, no
  stash. Nothing pushed.
- `docs/DEVELOPMENT_BRIEF.md` SHA-256 starts `274ecaed93400f51` (unchanged; it
  is excluded from git and must stay unchanged).
- `lexflow` at revision 0007; image `postgres:17` (PostgreSQL 17.11, Debian
  13); the `vector` extension is **not available** in this image.
- Running from an earlier session: API on 127.0.0.1:8000, Vite on 5173.
- Unattended resumption: **not available**. `ScheduleWakeup` only works inside
  a `/loop` session; scheduled cloud agents cannot reach this machine's files
  or database. Checkpoints (commits + this log) are the recovery mechanism.

## Milestones

| # | Milestone | Status |
|---|---|---|
| P3-M1 | Schema (0008), queue (claim, lease, outcome), status in API/UI | done |
| P3-M2 | Extractors (PDF, DOCX, TXT) with limits, in a child process; fixtures | pending |
| P3-M3 | Page-aware chunking and the worker loop | pending |
| P3-M4 | Text viewer, retry, live status, audit | pending |
| P3-M5 | pgvector (gated), embeddings provider, model command | pending |
| P3-M6 | Hardening, backfill command, docs, regression, migration gate | pending |

## P3-M1 — Schema, queue, processing status (done)

Grouping note: the worker *loop* (claim → extract → chunk → store) moved to
P3-M3, where the chunker it needs exists; M1 delivers the queue it uses.

- Migration **0008** (`server/migrations/versions/0008_document_extraction.py`,
  not applied to `lexflow`): new tables only. `document_extractions` (one job
  per stored document: status, reason code and message, attempts, lease,
  worker, counts, index status), `document_sections` (page text, or numbered
  parts with `page_number` null), `document_chunks` (section, page, exact
  character offsets, SHA-256; text must equal its offsets). Database checks:
  valid statuses, a reason exactly when failed/unsupported, a lease exactly
  while processing, offsets consistent. All cascade from `documents`.
- `server/lexflow/services/extraction_queue.py`: `queue` (on upload, in the
  same transaction; PDF/DOCX/TXT queued, images and .doc unsupported with a
  reason), `claim` (`FOR UPDATE SKIP LOCKED`, lease, attempts; jobs abandoned on
  their last attempt fail as `interrupted`), `complete` (only for the worker
  still holding the job; temporary failures re-queued until the attempt limit;
  success replaces earlier text in one transaction).
- Settings for limits, chunking, worker and embeddings (`server/lexflow/config.py`);
  the lease must outlast the extraction timeout; overlap < half a chunk.
- API: `DocumentOut.processing` (status, reason, page/section/chunk counts,
  index status; null for records without a file) on case detail, upload,
  restore, share and deleted listings.
- UI: status line per document in the Documents tab (waiting, extracting,
  extracted with pages or parts, failed with the reason, unsupported with the
  reason); the case refreshes every 3 s while a document is pending.
- Bug found by the database constraint and fixed before commit: `complete`
  cleared the lease before changing the status, so an autoflush wrote a
  "processing without a lease" row; the job row now changes all at once.

| Command | Result |
|---|---|
| `pytest` (server) | **504 passed** (468 + 22 masked prompt + 14 queue) |
| ruff, ruff format, mypy, OpenAPI drift | clean |
| `npm run check` | exit 0, 15 test files, build OK |

---

Checkpoint: P3-M1 committed (see `git log`). Next action: P3-M2 extractors.
