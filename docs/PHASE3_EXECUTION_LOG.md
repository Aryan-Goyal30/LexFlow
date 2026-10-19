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
| P3-M2 | Extractors (PDF, DOCX, TXT) with limits, in a child process; fixtures | done |
| P3-M3 | Page-aware chunking and the worker loop | done |
| P3-M4 | Text viewer, retry, live status, audit | done |
| P3-M5 | pgvector (gated), embeddings provider, model command | done, reduced: vector storage blocked (image) |
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
| `npm run check` | exit 0, 15 test files (151 tests), build OK |

## P3-M2 — Extractors (done)

- Dependencies via `pip-compile` (only these were added): `pypdf 6.21.1`
  (BSD-3-Clause), `python-docx 1.2.0` (MIT), `lxml 6.1.3` (BSD-3-Clause).
- `server/lexflow/extraction/`: `pdf.py` (page by page with real page numbers;
  empty pages kept so numbering stays true; owner-password-only PDFs read;
  password-protected → `encrypted`; damaged → `unreadable`; > page limit →
  `too-many-pages`; no text on any page → `no-text-layer` "OCR is not
  available"), `docx.py` (body paragraphs and tables in order; ZIP declared size
  checked before parsing → `too-large-unpacked`; damaged → `unreadable`; empty →
  `no-text`; page numbers null), `txt.py` (UTF-8, BOM removed), shared
  `normalise` (line endings, control characters, trailing spaces, blank-line
  runs; words untouched), `split_parts` (parts of about 20,000 characters at
  paragraph breaks for documents without pages), text-size limit
  (`text-too-large`).
- `runner.py`: extraction in a "spawn" child process; killed at the time limit
  (`timed-out`, not retried); a child that dies (`extractor-crashed`) is
  retryable; an extractor bug is reported as `extractor-error` without details.
- Fictional fixtures: `server/tests/document_fixtures.py` builds deterministic
  PDFs (exact text layer per page), scan-like and damaged PDFs, an encrypted
  PDF, Word files and a ZIP bomb; committed copies in
  `server/tests/fixtures/documents/` (README says they are fictional;
  `.gitattributes` keeps them byte-exact) are checked against the builder.

| Command | Result |
|---|---|
| `pytest tests/test_extractors.py` | **24 passed** (includes real child-process timeout, crash and bug tests) |
| `pytest` (server, full) | first run **1 failed, 527 passed**; then **528 passed** in 3 consecutive full runs |
| ruff, ruff format, mypy | clean (93 source files) |

**Open finding — intermittent failure (not caused by Phase 3 code):**
`tests/test_auth_committed.py::test_failures_and_lockout_survive_the_failed_requests`
failed once in a full run (Phase 2 code; it ran before any Phase 3 test file).
It passed 6 times alone, 3 times with the preceding files, and in 3 further
full runs. The failing assertion was not captured. Likely cause (unproven):
`AuditLog.record` deliberately swallows database errors (logging "Could not
write audit event") and the engine's `connect_timeout` is 3 s, so a slow
connection to Docker would drop one audit row and the test would see fewer
than 5 events. Same signature as the unexplained Phase 2 (M7) failure. Not
changed without evidence; full-run outputs are now saved so the next
occurrence shows its assertion.

## P3-M3 — Chunking and the worker (done)

- `server/lexflow/extraction/chunking.py`: chunks never cross a section (so
  each has one page, or none); `text == section_text[char_start:char_end]`;
  at most 1,200 characters; ends at a blank line, line break, sentence end or
  space (a single over-long word is cut); the next chunk starts about 200
  characters earlier at a word start; empty sections give no chunks; SHA-256
  per chunk; deterministic.
- `server/lexflow/worker.py` (`python -m lexflow.worker [--once]`): claims a
  job, reads the stored file and checks its SHA-256 (`file-changed`,
  `file-missing`, `storage-unavailable` (retried)), extracts in the child
  process, chunks, stores the outcome only while it still holds the job. On
  interruption (Ctrl+C or any error) it hands its job back to the queue. Logs
  ids and outcomes only, never text. Never downloads models.
- Tests: `tests/test_chunking.py` (14: coverage, exact offsets, page
  boundaries, overlap, natural breaks, long words, determinism, other sizes),
  `tests/test_worker.py` (12: 3-page PDF → page-numbered sections and chunks via
  the API; the real child-process path; Word parts without pages; scan → visible
  failure; changed and missing files; unsupported files never claimed; crash
  retried then failed; a worker that lost its job stores nothing; interrupted
  job handed back and finished by the next run; stale job of a dead worker
  recovered; reprocessing gives identical chunks; missing database message).
- Mutation checks (each restored byte-for-byte): ownership check removed,
  abandoned-job failure removed, SHA-256 check removed, hand-back removed, no
  overlap, no natural breaks. All six made tests fail.

| Command | Result |
|---|---|
| `pytest` (server, full) | **554 passed** (output saved) |
| ruff, ruff format, mypy (Windows and `--platform linux`) | clean (97 source files) |

## P3-M4 — Text viewer, retry, audit (done)

- API: `GET /api/documents/{id}/text?section=n` (staff who may view the case;
  one page or part at a time; 409 `text-not-available` with the reason until
  ready; 404 `section-not-found`; deleted documents 404; each read audited as
  `document.text_viewed` with the section number only, never text).
  `POST /api/documents/{id}/reprocess` (staff who may add documents; not on
  archived cases; 409 `already-processing` / `unsupported`, 422 `no-file`;
  audited as `document.reprocessed` with the previous status). Client accounts
  are refused by the existing staff-route sweeps.
- UI: `/app/cases/:caseId/documents/:documentId/text` — page or part N of M,
  previous/next, "Go to page", a plain message for empty (scanned) pages, the
  extractor name and a reminder to check against the original. Documents tab:
  "View text" only when ready; "Try again" only for failed documents and only
  for those who may upload. The case refreshes every 3 s while anything is
  waiting or processing.
- E2E: global setup now also starts the real worker (`scripts/e2e.py work
  --run-id …`) against the e2e database; teardown stops it (checked: no
  leftover processes, port 8001 free). `e2e/document-text.spec.ts` uploads the
  committed fictional fixtures: a 3-page PDF read page by page (UI and API),
  a scan that fails visibly and fails again honestly after a retry, client 403
  and outsider 404, deleted 404.
- Mutation checks (restored byte-for-byte): text served before ready, retry
  with view permission only, audit record removed, retry while queued, retry
  button without upload permission, "View text" for non-ready documents. The
  last one first survived; an assertion was added and it is now caught. All six
  caught.

| Command | Result |
|---|---|
| `pytest` (server, full) | **574 passed** (output saved) |
| ruff, ruff format, mypy (Windows and `--platform linux`), OpenAPI drift | clean (107 source files) |
| `npm run check` | exit 0, 16 test files (157 tests), API types in sync, build OK |
| `npx playwright test` (real API + real worker) | **32 passed** |

## P3-M5 — Embeddings: image check (blocked), provider gate, status command (done, reduced)

**Image compatibility — `pgvector/pgvector:pg17` FAILS; not used.**

| | current `postgres:17` | `pgvector/pgvector:pg17` | `pgvector/pgvector:pg17-trixie` |
|---|---|---|---|
| Digest | `sha256:2d2b8998d310…` | `sha256:ac08538c6f8b…` | `sha256:7a7e9f22015b…` |
| PostgreSQL package | 17.11-1.pgdg13+2 | 17.11-1.pgdg12+2 | 17.11-1.pgdg13+2 |
| Debian / glibc | 13 / 2.41-12+deb13u4 | **12 / 2.36-9+deb12u14** | 13 / 2.41-12+deb13u4 |
| pgvector | none | 0.8.7 | 0.8.7 |

Every database in the cluster uses the libc provider, collation `en_US.utf8`,
recorded collation version **2.41**. Running the existing data directory on the
`pg17` (bookworm, glibc 2.36) image would change the collation library under
existing text indexes (PostgreSQL warns of a version mismatch; indexes may
return wrong results until rebuilt). So the approved `pg17` tag was **not**
applied to `lexflow`, CI or `compose.yaml`.

`pg17-trixie` matches the current image exactly. Evidence (isolated: a
throwaway container `lexflow-pgvector-rehearsal` on tmpfs, no shared volume,
no published port): the fresh backup restored with `--exit-on-error`; recorded
and actual collation version both 2.41; `CREATE EXTENSION vector` gave 0.8.7;
a cosine-distance query worked; counts intact (7 cases, 28 documents, 6 users,
17 audit events, revision 0007); `REINDEX DATABASE` succeeded. Not tested: the
existing data directory itself under the new image (the swap). The container
is stopped, not removed (a safety check blocked the removal; remove it with
`docker rm lexflow-pgvector-rehearsal`).

**Blocker (owner decision needed):** switching to `pgvector/pgvector:pg17-trixie`
is a different tag from the one approved. Until the owner approves it (or
another image), vector storage (planned migration 0009, `vector(384)`), the
local `bge-small-en-v1.5` provider, the model download command and the
worker's indexing step are **not implemented**. No model was downloaded;
`fastembed` was not installed.

**Done instead (independent of the image):**
- `server/lexflow/embeddings.py`: `EmbeddingProvider` interface;
  `provider_for(settings)` returns nothing when embeddings are disabled and
  raises `EmbeddingsUnavailableError` (with the reason) for `local`. The worker
  checks this before claiming any job and the command exits 2 with the reason,
  instead of marking chunks "pending" that nothing would index (the M3 worker
  did that). Chunks are always stored with index status "disabled".
- `python -m lexflow.cli.models status` (read-only): the setting, the model
  name, what is in the model folder (never created), and whether the database
  server offers/has pgvector. On `lexflow` today: disabled; model folder does
  not exist; pgvector not offered.
- Tests: `tests/test_embeddings.py` (9). Mutation checks: refusal removed,
  worker check removed — both caught.

**Database gate for 0008 on `lexflow` — all checks passed; applied.**
1. Target: `server/.env` → `postgresql+psycopg` 127.0.0.1:5432 `lexflow`; only
   `lexflow-db-1` publishes that port. Revision 0007. Rows: alembic_version 1,
   audit_events 17, case_members 0, case_number_counters 2, cases 7, clients 6,
   documents 28, hearings 7, sessions 2, timeline_events 27, users 6.
2. Backup: `pg_dump -Fc` in the container, copied to
   `server/var/backups/lexflow-20261020-phase3-pre-0008.dump` (40,529 bytes,
   SHA-256 `2b058840737ef50c1d185f378e801182ed6057d8f8dc3ad19fa86b91be82a22e`,
   same inside and outside the container; git-ignored; 11 table-data entries).
3. Restored into a new scratch database `lexflow_p3_restore` (`--no-owner
   --exit-on-error`). Fingerprints (every table: columns, row count, md5 over
   every row) identical to `lexflow` taken right after the dump, and `lexflow`
   unchanged during the backup. `pg_dump --schema-only` identical (620 lines,
   excluding pg_dump's random `\restrict` keys).
4. Migration SQL (`alembic upgrade 0007:0008 --sql`): 3 `CREATE TABLE`, 2
   `CREATE INDEX`, the `alembic_version` update; no `ALTER`/`DROP`/`DELETE` of
   existing objects. New foreign keys cascade from documents to the new
   tables only.
5. Rehearsal on `lexflow_p3_restore` only (the script refuses other names):
   upgrade 0008 → existing 10 tables identical, 3 new tables empty; downgrade
   0007 → whole database identical to before; upgrade 0008 again → identical.
6. Re-checked the backup checksum and that `lexflow` was still identical, then
   `alembic upgrade 0008` (exit 0). After: revision **0008 (head)**; existing
   10 tables identical (same columns, counts, checksums); new tables empty;
   `alembic check`: no differences. Scratch `lexflow_p3_restore` (at 0008) left
   for inspection.

Existing documents have no extraction job yet (nothing is queued by the
migration); the explicit backfill command comes in P3-M6.

| Command | Result |
|---|---|
| `pytest tests/test_embeddings.py tests/test_worker.py` | **21 passed** |
| ruff, ruff format, mypy (Windows and `--platform linux`) | clean (110 source files) |

---

Checkpoint: P3-M5 committed (see `git log`); `lexflow` at 0008. Next action:
P3-M6 — backfill command (`python -m lexflow.cli.documents queue-extraction`),
docs (README, server README, `.env.example`, ADRs), full regression, restart
the API on the new code and start the worker.
