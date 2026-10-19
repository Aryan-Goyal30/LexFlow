# Phase 1 Execution Log

Durable checkpoint for the autonomous Phase 1 run (backend and persistence).
Update after every milestone and before stopping. Newest entries at the bottom
of each section.

## Ground rules for this run

- Do **not** commit or push. All work stays in the working tree for review.
- `docs/DEVELOPMENT_BRIEF.md` is untracked and must stay byte-for-byte
  identical. Fingerprint at start of run:
  `sha256 274ecaed93400f51dd47c42337fbd6e101aa6be366b80d977d1522359b34c2ec`,
  20,737 bytes.
- Starting point: branch `master`, HEAD `eee4263` (11 Phase 0 commits on top of
  `b1bd5c3`). Working tree clean apart from the untracked brief.
- Out of scope: real authentication, AI/LLM, precedent retrieval, OCR/text
  extraction, pgvector search, deployment.

## Environment (observed 2026-10-19)

| Tool | Version |
|---|---|
| Docker | 29.8.2 (Docker Desktop), Compose v5.6.0 |
| Python | 3.12.3 (`py -3.12`) |
| Node / npm | 24.19.0 / 11.17.0 |
| Ports 5432, 8000, 5173 | free at start |

## Milestone status

| Milestone | Status |
|---|---|
| M1 Backend foundation | **done** (all acceptance criteria verified) |
| M2 Reference data + sample-data loader | **done** (all acceptance criteria verified) |
| M3 Cases API | **done** (all acceptance criteria verified; review findings fixed) |
| M4 Document storage + upload API | **done** (all acceptance criteria verified, incl. live restart test) |
| M5 Frontend API integration | **done** (MSW tests; real stack verified by E2E; review findings fixed) |
| M6 Documents tab integration | **done** (MSW tests; real stack verified by E2E; review findings fixed) |
| M7 E2E, CI, documentation | **done** (E2E 6/6 locally; CI written, not run on GitHub) |

## Decisions taken during the run

(Implementation details not fixed by the approved plan, with reasons.)

- **Dependency pinning:** pip-tools. `requirements.in` / `requirements-dev.in`
  list direct deps; `requirements.txt` / `requirements-dev.txt` are fully pinned.
- **`httpx2` instead of `httpx`:** Starlette 1.9's test client deprecates
  `httpx` in favour of `httpx2` (a published package it imports first).
- **`tzdata` dependency:** Windows has no system time-zone database, and
  `zoneinfo` needs it for Asia/Kolkata.
- **Settings default `LEXFLOW_ENV=production`:** development-only behaviour
  (sample-data loading) must be switched on deliberately in `server/.env`.
- **Compose file and `.env` live in `server/`:** one `.env` serves Compose,
  the API, Alembic and the tests.
- **Postgres image `postgres:17`:** official image; pgvector is out of scope.
- **Alembic URL never in `alembic.ini`:** read from settings, or passed by the
  tests via `config.attributes`, so no password lives in a tracked file.
- **Hearing time nullable:** a new case's first hearing has no time until the
  court lists it. The old front end invented "10:30"; the server stores NULL.
- **Users.email nullable:** the sample data has no e-mail address for four of
  the five advocates; none is invented.
- **Timeline actor:** `timeline_events.actor_id` NULL = recorded by the system
  without a signed-in user (always so in Phase 1).
- **Duplicate document names:** unique index on `(case_id, lower(name))`,
  matching the existing front-end rule.
- **Tests' database safety:** `TEST_DATABASE_URL` must name a database whose
  name contains `test`; the suite drops and recreates it each run.
- **API server binds to loopback only:** `python -m lexflow` exits with code 2
  for any non-loopback `LEXFLOW_API_HOST`.
- **Sample-data source of truth stays `src/data/mockData.ts`:**
  `scripts/export-sample-data.mjs` compiles it with the project's TypeScript and
  writes `server/lexflow/seed/sample_data.json`; `--check` fails on any drift.
  Generated files are excluded from Prettier.
- **Sample UUIDs:** `uuid5(7f27cbaa-4c8e-4a53-a1bc-1d3f2536f8a0, "<kind>:<legacy id>")`.
- **Advocates are users:** role `Advocate`, keyed by name (the source has no ids
  for them). Only the demo user has an e-mail address; none invented.
- **Seed conflicts are loud:** inserts use `ON CONFLICT (id) DO NOTHING`; a sample
  case number already used by a real case aborts the whole load (exit 1).
- **Counters:** the seed raises each year's counter to at least the highest
  sample number (`GREATEST`), so new numbers never collide with sample ones.
- **Test DB URLs are `sqlalchemy.URL` objects** (repr masks the password).
- **"Today" is a dependency (`lexflow.clock.get_today`)** in the configured time
  zone; tests freeze it. Case-number years and the past-hearing rule use it.
- **Case numbers:** atomic `INSERT … ON CONFLICT (year) DO UPDATE … RETURNING`;
  a year's first counter starts above any existing `LF-<year>-` number.
- **`nextHearing`:** earliest hearing on/after today, else the latest past one
  (the UI marks it "date has passed"). Never stored.
- **Ids that aren't UUIDs** (e.g. old links like `case-1005`) return 404
  `case-not-found`, not 422.
- **PATCH:** only fields present change; `courtName`/`opposingParty` may be null
  (clears), other fields may not. Any real change adds a "Case details updated"
  timeline entry with `actor: null`; no-op PATCH adds nothing. `nextHearing` is
  not patchable (hearing management belongs to a later phase).
- **Request bodies forbid unknown fields** (422), so typos aren't silently ignored.
- **Document order:** newest first (upload date desc, then created, then name).
- **OpenAPI post-processing (`lexflow/openapi.py`):** every 4xx/5xx is
  documented as `application/problem+json` with the `Problem` schema; FastAPI's
  `HTTPValidationError` is removed; 422 dropped where it can't occur.
- **Storage keys:** `uuid4().hex`, sharded `var/uploads/<key[:2]>/<key>`; the
  user's filename is only a label. Staging files live in `var/uploads/.staging`
  (same volume, so the final move is an atomic rename).
- **Upload order:** stream to staging (hash, size, content check) -> insert row
  + flush (duplicates fail here) -> move file -> commit; rollback + delete file
  on failure. **Delete order:** commit row removal, then delete file (worst case
  an orphaned file, never a dangling record).
- **Upload error codes** (problem `code`): `unsupported-type` 415,
  `content-mismatch` 415, `empty` 422, `duplicate` 409, `too-large` 413,
  `invalid-name` 422, `case-not-found` 404. Download: `document-not-found`,
  `no-file` (sample record), `file-missing` (404).
- **Size limit while streaming:** `UploadLimitMiddleware` refuses a declared
  Content-Length over limit + 64 KiB multipart overhead before reading, counts
  streamed bytes otherwise, and replaces the framework's 400 (form parser) with
  the 413 problem. The service then checks the exact file size.
- **Filenames:** last path component only; control/format characters removed
  (incl. U+202E); the WHATWG browser escapes `%22`, `%0D`, `%0A` decoded, nothing
  else. A name with no stem (".pdf") is unsupported.
- **Downloads:** content type from the server's check (never the client's);
  `nosniff`, `no-store`; inline for PDF/images/text, attachment for Word;
  sandbox CSP for inline images/text (not PDF: browser viewers refuse
  sandboxed documents). Filenames via RFC 5987 `filename*` + ASCII fallback.
- **Security hardening from the M1–M3 review (see below):** `LocalOnlyMiddleware`
  refuses non-loopback `Host` (400 `invalid-host`, DNS rebinding) and
  state-changing requests from non-loopback `Origin` (403 `forbidden-origin`,
  CSRF incl. form-based uploads). `LEXFLOW_ALLOWED_HOSTS` configures the hosts.

## Log

### Run start

- Inspected git (HEAD `eee4263`, clean except brief), Docker, Python 3.12,
  Node. Recorded brief fingerprint above.

### M1 — Backend foundation (done)

Files added: `server/` — `lexflow/{__init__,__main__,config,db,domain,errors,main,models}.py`,
`lexflow/api/{__init__,health}.py`, `migrations/{env.py,script.py.mako}`,
`migrations/versions/0001_initial_schema.py`, `alembic.ini`, `compose.yaml`,
`.env.example`, `pyproject.toml`, `requirements*.in/.txt`, `README.md`,
`tests/{__init__,conftest,test_health,test_migrations}.py`. Local only (ignored):
`server/.env` (random password, never printed), `server/.venv/`.
Changed: `.gitignore` (Python caches, `server/var/`, Playwright output),
`eslint.config.js` (ignore `server/.venv`, `server/var`, Playwright output).

Verified (commands run from `server/` unless noted):

| Command | Result |
|---|---|
| `docker compose up -d --wait` | `lexflow-db-1` healthy, port `127.0.0.1:5432` |
| `.venv\Scripts\python -m pytest -q -W error::DeprecationWarning` | 6 passed |
| `.venv\Scripts\ruff format --check .` / `ruff check .` | clean |
| `.venv\Scripts\mypy` (strict) | no issues, 15 files |
| `.venv\Scripts\python -m alembic upgrade head` (dev DB) | at `0001 (head)` |
| `python -m lexflow`, `GET /api/health` | 200 `{"status":"ok","database":"ok"}` |
| `docker compose stop db`, `GET /api/health` | 503 `unavailable`; back to 200 after `start` |
| `GET /docs` | 200 |
| Listening address on :8000 | `127.0.0.1` only |
| `LEXFLOW_API_HOST=0.0.0.0 python -m lexflow` | refused, exit 2 |
| API log scanned for DB password / URL | 0 occurrences |
| repo root: `npm run check` | exit 0 (lint, format, typecheck, 55 tests, build) |

### Incident during M2 — secret in test output (resolved)

A failing pytest run printed a scratch-database URL including the local
password (pytest shows test arguments in tracebacks). Fixed and verified:
- Test helpers now pass `sqlalchemy.URL` objects; their repr is
  `lexflow:***@…`. A deliberately failing probe test confirmed 0 password
  occurrences in `--tb=long` output (probe file deleted afterwards).
- The local PostgreSQL password was rotated (`ALTER ROLE` via stdin) and
  `server/.env` updated (3 occurrences). Nothing printed. The API was restarted.

### M2 — Reference data and sample-data loader (done)

Files added: `scripts/export-sample-data.mjs`, `server/lexflow/seed/{__init__,__main__,loader}.py`,
`server/lexflow/seed/sample_data.json` (generated), `server/lexflow/schemas.py`,
`server/lexflow/api/reference.py`, `server/tests/{test_seed,test_reference}.py`.
Changed: `server/lexflow/main.py` (router), `server/tests/conftest.py`,
`server/tests/test_migrations.py` (URL objects), `.prettierignore` (generated files).

| Command | Result |
|---|---|
| `node scripts/export-sample-data.mjs --check` | matches `src/data/mockData.ts` |
| `pytest -q -W error::DeprecationWarning` | 19 passed |
| `ruff format --check`, `ruff check`, `mypy` | clean (22 files) |
| `python -m lexflow.seed` (dev DB) | loaded 5 users, 6 clients, 6 cases, 5 hearings, 22 events, 26 documents |
| `python -m lexflow.seed` again | "already loaded; nothing to add", exit 0 |
| `LEXFLOW_ENV=production python -m lexflow.seed` | refused, exit 2 |
| DB check | every row `is_sample`; counters 2025→331, 2026→489 |
| live `GET /api/clients`, `/api/advocates` | 6 clients, 5 advocates, camelCase, `isSample: true` |

### M3 — Cases API (done)

Files added: `server/lexflow/{clock,openapi}.py`, `server/lexflow/services/{__init__,case_numbers,cases,formatting}.py`,
`server/lexflow/api/cases.py`, `server/tests/{test_cases,test_openapi}.py`.
Changed: `server/lexflow/{schemas,main}.py`.

| Command | Result |
|---|---|
| `pytest -q -W error::DeprecationWarning` | 55 passed (incl. 12-thread allocator and 8-thread API concurrency tests with real commits) |
| `ruff format --check`, `ruff check`, `mypy` | clean (31 files) |
| live `GET /api/cases` | 6 summaries, derived next hearings, doc counts |
| live `GET /api/cases/case-1005` (legacy id) | 404 problem `case-not-found` |
| live `POST /api/cases` invalid | 422 problem with camelCase field errors |
| live `GET /api/hearings/upcoming` | `[]` (all fixed sample dates are before 2026-10-19) |

Independent read-only review of M1–M3 launched as workflow `wf_8bd69c8e-8f6`
(3 lenses + adversarial verifier). Act on confirmed findings when it reports.

### Independent review of M1–M3 (workflow `wf_8bd69c8e-8f6`)

3 read-only reviewers (data integrity, security, contract/tests) + 1 adversarial
verifier. 11 candidate findings: **7 confirmed**, 4 refuted. All 7 fixed:

| Severity | Finding | Fix | Regression test |
|---|---|---|---|
| high | No Host check: DNS rebinding bypasses loopback bind | `LocalOnlyMiddleware` Host allow-list (+ Origin check for writes) | `test_security.py` host/origin tests; protection removal makes them fail |
| medium | Concurrent PATCH could double-record / mis-record history | `SELECT … FOR UPDATE` in `update_case` | 6-thread double-submit test: exactly 1 entry; fails without the lock |
| medium/low (x2) | NUL in text -> DB error -> 500 | `InputModel` rejects NUL -> 422 field error | `test_nul_characters_are_a_field_error` |
| medium/low (x2) | Unhandled errors logged message + SQL params; logged twice | `CatchAllMiddleware` + log type/frames only; engine `hide_parameters=True` | marker-string test: absent from log and response |
| low | Malformed JSON reported field "1" | map `json_invalid` to field `request` | `test_malformed_json_names_the_request_not_an_offset` |

Also added the refuted-but-reasonable test gaps (length/whitespace limits).

### Incident — escape sequences in scripted edits (resolved)

Backslash escapes in heredoc Python scripts were unescaped before reaching the
shell: one log string got a real line break (syntax error) and the NUL check got
a literal NUL byte. Both caught by ruff/mypy, repaired with `chr()`-built text,
and verified (0 NUL bytes). Python `write_text` had also turned several files to
CRLF; all files under `server/` normalised to LF and verified.
Rule from now on: no backslash escapes in heredoc edits; use the Edit tool or
`chr()`, and write bytes.

### M4 — Document storage and upload API (done)

Files added: `server/lexflow/{storage,upload_limit,security}.py`,
`server/lexflow/services/{documents,uploads}.py`, `server/lexflow/api/documents.py`,
`server/tests/{test_documents,test_security}.py`.
Changed: `server/lexflow/{main,errors,config,db,schemas}.py`,
`server/lexflow/services/cases.py`, `server/pyproject.toml` (allowed confusable "–").

| Command | Result |
|---|---|
| `pytest -q -W error::DeprecationWarning` | **148 passed** |
| `ruff format --check`, `ruff check`, `mypy` (strict) | clean (39 files) |
| bug re-introduction: Host check / Origin check / PATCH lock removed | matching tests fail (3/3/1), files restored byte-for-byte |
| live upload -> restart DB container + API process -> download | byte-identical, safe headers |
| live cross-site upload / rebinding Host | 403 / 400 |
| live delete | 204, row and stored file removed; dev DB back to 26 sample docs |

### M5 - Frontend API integration (done; real stack verified by the M7 E2E tests)

Added: `@tanstack/react-query` (dependency); `msw`, `openapi-typescript` (dev).
`scripts/api-types.mjs` generates `src/services/api/schema.gen.ts` from
`server/openapi.json` (`npm run api:check` fails on drift);
`scripts/export-sample-data.mjs` keeps `server/lexflow/seed/sample_data.json` in
step with `src/data/mockData.ts` (`npm run sample-data:check`).
New: `src/services/api/{client,lexflow}.ts`, `src/hooks/useCases.ts`,
`src/lib/queryClient.ts`, `src/components/ui/QueryState.tsx`, `src/test/mockApi.ts`
(MSW fake API mirroring the server contract), `src/pages/CasesPage.test.tsx`.
Removed: `src/context/CasesContext.tsx` (+ test), `src/lib/ids.ts`; case numbers are
now allocated by the server only.

Decisions: the form sends `leadAdvocateId` (an id, not a name); server field errors
are mapped beside their fields; no retry on 4xx; tests mount MSW at the network
boundary and use Node's File/Blob/FormData because jsdom's FormData cannot be
read by Node fetch. Runtime case data no longer comes from `mockData.ts` (only the
mock signed-in user, which is Phase 2 auth work).

| Command | Result |
|---|---|
| `npm run check` (lint, format, typecheck, api:check, sample-data:check, test, build) | exit 0; 6 files, **70 tests passed** |
| bug re-introduction: server field errors not mapped / empty DB not distinguished | matching tests fail, files restored byte-for-byte |

### M6 - Documents tab on the real API (done; real stack verified by the M7 E2E tests)

`DocumentsTab.tsx`: sequential uploads with progress text, server rejection
messages shown per file, Open uses `downloadUrl`, per-document delete state and
errors, sample records labelled "sample record, no file attached".

### M7 - End-to-end tests, CI, README, ADRs (done; CI not run on GitHub)

Added: `@playwright/test` 1.64.1 (dev dependency, exact pin), `playwright.config.ts`,
`e2e/{cases.spec.ts,global-setup.ts,global-teardown.ts,support/backend.ts}`,
`server/scripts/e2e.py` (prepare: recreate `lexflow_e2e`, migrate, seed, empty
`server/var/e2e-uploads`; serve: API on 127.0.0.1:8001), `npm run e2e`,
`docs/adr/` (README + 0001-0010). Rewrote `README.md`; extended `server/README.md`
(sample data, uploads, security model, e2e). CI now has three jobs: frontend
(+ api:check, sample-data:check), backend (postgres:17 service with trust auth, no
stored password; ruff, ruff format, mypy, alembic upgrade, pytest, OpenAPI check), e2e.
Changed: `tsconfig.json` (type-checks e2e/ and playwright.config.ts),
`vitest.config.ts` (`include: src/**/*.test.*`, so Vitest ignores the Playwright spec),
`.gitignore`/`.prettierignore`/`eslint.config.js` (`e2e/.state`).

Decisions: credentials stay inside the Python process (Node never sees the DB URL);
the API's pid is kept in `e2e/.state/api.pid` so a test can restart it and teardown
stops whichever process is current; the e2e database name must contain `e2e`.

| Command | Result |
|---|---|
| `npx playwright test` (Chromium, real Vite + API + PostgreSQL) | **6 passed**: list from API, create + reload, upload/open/download bytes/delete, server rejects fake PDF, API restart keeps case and file, unknown case |
| api.log after run | 2 startups (restart really happened); 0 occurrences of the DB password or `postgresql` |
| bug re-introduction: `delete_document` rolls back instead of committing | E2E test 3 fails, file restored byte-for-byte |
| pip dry run for Linux / CPython 3.12 (manylinux) with both requirement files | all pins resolve |
| CI YAML parsed with js-yaml | 3 jobs (10/9/8 steps); not run on GitHub (no remote, no push) |
| backend: ruff check, ruff format --check, mypy, alembic upgrade head, pytest, export_openapi --check | all clean; **148 passed** |
| `npm run check` | exit 0; 6 files, **70 tests passed**, build ok |

Incident: the first `npm run check` after adding e2e/ failed because Vitest collected
`e2e/cases.spec.ts`; fixed with an explicit `include` in `vitest.config.ts`.

### Independent review of M5-M7 (workflow `wf_917da35c-d7f`)

Three read-only reviewers (front end, E2E/CI, docs) and an adversarial verifier.
The first attempt stopped at a usage limit after one reviewer; it was resumed
from its run id (the finished reviewer replayed from cache). 14 candidates:
12 confirmed, 2 refuted (both fixed anyway, cheaply).

| Severity | Finding | Fix | Test (fails when the bug is put back) |
|---|---|---|---|
| medium | Two removals in flight: `mutate()` per-call callbacks fire only for the latest call, so the first one's error was lost and its button stuck on "Removing" | `mutateAsync` per removal; errors kept per document | `reports each removal separately when two are in flight at once` |
| medium | API down behind the Vite proxy gives an empty `500 text/plain` (confirmed live), shown as "status 500" | any 5xx without a problem document means "Can't reach the LexFlow server" | `explains when the dev proxy answers for an API that is not running` |
| medium | A failed background refetch replaced the workspace, case list and dashboard with an error, losing upload feedback | keep data on screen with `StaleDataNotice` + Try again; full error only without data or for 404 | `keeps the case on screen...`, `keeps the list on screen...` |
| low | Switching tabs mid-upload unmounted the Documents tab: progress and results lost, a second batch could start | Documents panel stays mounted, hidden | `keeps upload progress and results when the user switches tabs` |
| low | Files dropped during an upload were silently ignored | notice "... not added: wait for the current upload to finish"; `dropEffect = none` | `says so when files are dropped while an upload is running` |
| low | Open links ignored `VITE_API_BASE_URL` (server `downloadUrl` assumes `/api`) | `documentDownloadUrl()` built with `apiUrl` | upload test checks the absolute URL |
| low | Teardown could kill a stale, reused PID after an interrupted run; PID file deleted before the stop was confirmed | setup forgets any old PID first; file removed only after the API stopped | live: decoy process planted in `api.pid`, setup forced to fail, decoy survived |
| low | Missing Python reported as "exit signal" | report the spawn error with a hint; `python3` fallback off Windows | live: `Could not run does-not-exist-python: ... ENOENT. Set LEXFLOW_PYTHON...` |
| low | Log status table still said M5-M7 "not started" | updated | - |
| low | MSW fake's unsupported-type message shorter than the server's | same wording (all fake messages compared with the server source) | - |
| low | README: dashboard panels "independent", tests cover "every page" | reworded precisely; added Practice Overview loading/empty test | `shows loading states, then empty states for an empty database` |
| (refuted) | 404 on delete shown as failure | treated as already removed | `treats a document already removed elsewhere as removed` |
| (refuted) | CI artifact might skip the hidden `e2e/.state/api.log` | `include-hidden-files: true` anyway | - |

| Command | Result |
|---|---|
| bug re-introduction for the 7 front-end fixes | each matching test fails; files restored byte-for-byte |
| `npm run check` | exit 0; 6 files, **78 tests passed**, build ok |
| `npx playwright test` | **6 passed**; nothing left listening on 5174/8001 |

### Check of the review fixes (workflow `wf_de25bd90-4cf`)

Two independent checkers. Both found that the busy-drop fix set
`dropEffect = 'none'` on dragover, which makes a real browser skip the drop
event, so the notice could never appear outside jsdom. Removed; the test now fires
dragover first and asserts dropEffect is not 'none' (fails when the line is put
back). Also: Windows' `python` store alias exits 9009 instead of failing to start;
that exit code now gets the same hint.

| Command | Result |
|---|---|
| `npm run check` | exit 0; 6 files, **78 tests passed**, build ok |
| `npx playwright test` | **6 passed** |
| backend: ruff, ruff format, mypy, pytest, OpenAPI check | clean; **148 passed** |

### Final audit and approved fixes (workflow `wf_7f165b98-658`)

Read-only audit (three auditors plus an adversarial verifier) and a replay of the
proposed eight commits in a scratch copy. The user approved fixing everything
below before committing.

| Issue | Fix | Evidence |
|---|---|---|
| I1: E2E teardown could signal a dead or reused pid (a test worker's restarted API died with the worker; the pid file stayed) | Each start passes a random `--run-id` to `e2e.py serve` and records `{ pid, runId }` (`e2e/.state/api.json`). A process is stopped only if the OS reports that pid still running `e2e.py` with that run id (`/proc/<pid>/cmdline`, `Win32_Process`, `ps`). Health is only supplementary. Start-up `exit`/`error` events fail fast; a failed start stops only its own child. The API is spawned detached. Global setup clears stale records, stopping a process only if its identity is proven. | `e2e/harness.spec.ts` (5 tests, decoy processes); weakening the identity check either way fails 2 of them. Live: unrelated pid in a stale record survives a full run and a failed setup; a real orphaned API is identified and stopped. |
| I2: backend tests could write to `server/var/uploads` | `conftest.py` points `LEXFLOW_UPLOAD_DIR` at a temporary folder for the session (removed at exit); `test_main.py` guards it | Dev upload folder identical before and after the suite; the Origin-check mutation that leaked 3 files before now leaves it unchanged |
| I3: batch upload failures could omit the file name | `withFileName()` prefixes the name when the server's or client's message lacks it | 2 new tests (oversized file in a batch, unreachable server); both fail without the fix |
| Bind refusal tested by hand only | `server/tests/test_main.py`: 0.0.0.0, ::, LAN addresses, a host name and empty are refused with no server start; loopback hosts start | 6 tests fail when the check is removed |
| Size-limit tests didn't prove early stopping | Tests drive the ASGI app with a chunked `receive()`: declared oversize gets 413 with 0 body reads; streamed oversize stops reading one chunk past the limit | each fails when its mechanism is removed |
| Upload route `async` but synchronous work | Route and service are plain `def` (FastAPI runs them in the thread pool; the form is still received on the event loop) | `test_upload_work_runs_off_the_event_loop` fails if the route is made `async` again |
| Doc nits | `.prettierignore` comment; README says copy `.env.example` to `.env.local` | - |
| Brief could be staged by a broad `git add` | local `.git/info/exclude` entry `/docs/DEVELOPMENT_BRIEF.md` (no tracked file changed) | `git check-ignore -v` -> `.git/info/exclude:9` |

Orphan files: the 3 files in `server/var/uploads` were identified from metadata
only (written 00:34:18Z, 5 s into the 00:34:13Z Origin-check mutation run; 9
bytes each = the cross-site test payload; 3 = its parametrised origins; no
reference in the dev, test or e2e database; nothing else in the folder) and
deleted. Contents were not read.

| Command | Result |
|---|---|
| ruff check / ruff format --check / mypy | clean (44 files formatted; 42 type-checked) |
| alembic current / upgrade head | 0001 (head) / 0 steps |
| pytest -q -W error::DeprecationWarning | **160 passed** |
| export_openapi.py --check | up to date |
| `npm run check` | exit 0; 6 files, **80 tests passed**; build ok |
| `npx playwright test` | **11 passed** (6 flows + 5 harness); no e2e API process left, ports 8001/5174 free |

## Next action

Phase 1 (M1-M7) implemented and verified locally; reviews done and fixed.
User actions: review the working tree, decide on commits, add a GitHub remote
so CI can run.
