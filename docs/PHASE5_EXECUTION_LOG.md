# Phase 5 execution log — AI case analysis with Google Gemini

Started 2026-10-20. Scope: `docs/DEVELOPMENT_BRIEF.md` §4 Phase 5 and
`docs/PHASE5_PLAN.md` (decisions D1–D5 approved, plan §9). No Phase 6–7 work.

## How to resume (read this first)

1. `git log --oneline` — milestone commits start with `Phase 5 M<n>`.
2. Read `docs/verification/phase5/checkpoint.json` (machine-readable) and the
   **Checkpoint** line at the end of this file.
3. Check `alembic current` (in `server/`) against the checkpoint. The live
   `lexflow` database is at **0011** since M8 (applied 2026-10-20 with the
   owner's approval).
4. Resume at the first milestone not marked done below.
5. Unattended resumption is not available in this environment; these files
   and the commits are the recovery mechanism.

## Start state (verified)

- `master` at `cb40bcc` (plan committed), clean; no remote; nothing pushed.
- `docs/DEVELOPMENT_BRIEF.md` SHA-256 `274ecaed93400f51dd47c42337fbd6e101aa6be366b80d977d1522359b34c2ec`.
- `server/.env` is git-ignored (`.gitignore:10:.env`); no `.env` file is
  tracked. It has no `GEMINI_API_KEY` line (checked by counting matching
  lines; the file's values were never printed).
- Live `lexflow`: revision 0010, `pgvector/pgvector:pg17-trixie`, volume
  `lexflow_pgdata`; embeddings disabled; judgment collection empty; API and
  worker running the Phase 4 code.

## Owner decisions (approved; full text in `PHASE5_PLAN.md` §9)

| | Decision | Applied as |
|---|---|---|
| D1 | Synthetic or sample cases only; no real client material to Gemini; production use needs a separate privacy, confidentiality and provider-terms review | `LEXFLOW_AI_ALLOW_CLIENT_DATA=false` (default) refuses non-sample cases in the API **and** the worker; transmission notice + explicit confirmation before every run |
| D2 | Gemini API, configurable model, key from `GEMINI_API_KEY` in `server/.env` set by the owner | `GEMINI_MODEL` has no default; key is a `SecretStr`; missing key/model → "unavailable" with the reason, never a crash |
| D3 | Official `google-genai` SDK, pinned | `google-genai==2.31.0` via pip-compile |
| D4 | Administrator + advocates on the case start runs; archived cases refused; every read authorised; audit without secrets or prompt text | `Action.RUN_ANALYSIS` = admin, lead, associate; reads need `view` |
| D5 | Usable with no judgments; say so; never invent | `precedentsAvailable: false` + "No precedents were available for comparison" |

**Model documentation check (D2).** Google's model list, structured-output
support and prices change often and were not verified against Google's
documentation in this run (no Gemini call and no reliance on remembered
model names). The SDK's request types were inspected offline
(`GenerateContentConfig.response_json_schema`, `HttpOptions.timeout` in
milliseconds, `HttpRetryOptions`, `errors.ClientError/ServerError`). The
owner must choose `GEMINI_MODEL` from Google's current list and check its
structured-output support and pricing before the first real run.

## Milestones

| # | Milestone | Status |
|---|---|---|
| M0 | Owner decisions D1–D5 | done (approved 2026-10-20) |
| M1 | Contract, settings, migration 0011 (scratch only), output schema | done (`d681326`) |
| M2 | Evidence assembly + prompt v1 | done (`392f3b4`) |
| M3 | Provider layer | done (`5128eb7`) |
| M4 | Validation | done (`219945e`) |
| M5 | Runs: API, worker, audit, authorisation | done (`8e6430a`) |
| M6 | User interface | done (`e57aebc`) |
| M7 | Verification and documents | done |
| M8 | Live migration 0011 + manual smoke | **migration applied and verified** (2026-10-20, owner-approved); **real Gemini smoke test run**: 1 success after 3 failures; two open items (see M8e) |

## M1 — Contract, settings, migration 0011, output schema (done)

- **Dependency:** `google-genai` added to `server/requirements.in`;
  `requirements.txt` recompiled with pip-compile (existing pins unchanged;
  15 new pins: `google-genai 2.31.0`, `google-auth`, `httpx 0.28.1`,
  `httpcore`, `cryptography`, `requests`, `urllib3`, `certifi`,
  `charset-normalizer`, `websockets`, `tenacity`, `sniffio`, `distro`,
  `pyasn1`, `pyasn1-modules`); installed with `pip-sync`; `pip check` clean.
  The SDK makes no retry by default (`retry_options=None`); LexFlow owns
  retries.
- **Settings** (`lexflow/config.py`, documented in `server/.env.example`
  without values): `LEXFLOW_AI_PROVIDER` (`disabled` | `gemini` |
  `scripted`), `GEMINI_API_KEY` (`SecretStr`; blank = missing),
  `GEMINI_MODEL` (no default; checked characters), timeout 90 s, input
  60,000 characters, 20 documents, 40 passages, 8 precedents, 16,384 output
  tokens, 10 runs per user per hour, 3 attempts,
  `LEXFLOW_AI_ALLOW_CLIENT_DATA=false`. `scripted` is refused unless the
  environment is test/development **and** the database name contains
  "test" or "e2e".
- **Contract** (`lexflow/schemas.py`): `AnalysisRunIn` (document ids +
  `confirmTransmission`), `AnalysisSetupOut`, `AnalysisRunOut` /
  `AnalysisRunSummaryOut`, `AnalysisResultOut` (facts with one verified
  `source` each, issues, precedents with judgment id and passage,
  contradictions with ≥ 2 sources, `insufficientEvidence`,
  `precedentsAvailable`, `removed{count, reasons}`); no `relevance` score
  and no outcome assessment. `CasePermissions.canRunAnalysis`.
- **Access:** `Action.RUN_ANALYSIS` (admin, lead, associate; refused on
  archived cases by the existing archive rule).
- **Model output** (`lexflow/analysis/output.py`): the JSON shape asked of
  the model (plain JSON Schema, no `$ref`, no string-length keywords) and a
  defensive parser: the answer must be a JSON object with list-typed keys,
  otherwise `invalid-output`; malformed items inside lists are dropped and
  counted; extra keys ignored; an outcome assessment noted for discarding.
- **Migration 0011** (`analysis_runs`, additive). Autogenerated against the
  scratch database `lexflow_autogen_p5_test` on the scratch server
  (127.0.0.1:55432), reviewed, then on scratch: upgrade → `alembic check`
  clean → downgrade 0010 → upgrade → `alembic check` clean. Checks: status
  values, reason iff failed, lease iff running, result iff ready, lengths;
  indexes `(case_id, created_at)`, `(status, available_at)`,
  `(requested_by_id, created_at)` and a partial unique index allowing one
  queued/running run per case. Deviation from the plan: `available_at`
  (pause before a retry) and `selection` (request) columns added; the queue
  index is on `available_at` rather than `created_at`. **Not applied to
  live.**
- **Tests:** `tests/conftest.py` forces `LEXFLOW_AI_PROVIDER=disabled` and
  blank Gemini settings for every test (whatever `server/.env` says) and an
  autouse fixture makes constructing a real `google.genai.Client` fail.
  New `test_analysis_config.py`, `test_analysis_output.py`;
  `test_migrations.py` expects `analysis_runs`.
- **Pre-existing test defect fixed:**
  `test_extraction_queue.py::test_workers_get_the_oldest_waiting_job_with_a_lease`
  compared a real upload time with a fixed `NOW` of 2026-10-20 09:00 UTC and
  began failing once the real clock passed it; both jobs' times are now set
  explicitly.

## M2 — Evidence assembly and prompt v1 (done)

- `lexflow/analysis/evidence.py`: the evidence of one run.
  - Case context (title, practice area, status, court, opposing party,
    summary ≤ 3,000 characters, last 30 timeline events) is background only
    and cannot be cited.
  - `D1…` passages come only from the **selected** documents **of this
    case** that are not deleted and whose text is `ready`; other selected
    ids are reported as "without text". Documents in upload-date then name
    order. Each document's first passage is taken first, then the passages
    sharing most words with the case title and summary; limits on
    documents (20), passages (40) and characters (60,000 including the
    context); `truncated` is recorded.
  - `J1…` passages: keyword search of the judgment collection (Phase 4
    `judgments.keyword`) with the case's eight most frequent content words
    joined by "or"; at most 8 and at most a quarter of the character budget.
    With the empty live collection there are none (D5).
  - `Evidence.record()` (stored with the run): ids → document/chunk/page or
    judgment/chunk/rank plus content SHA-256; **no text**.
- `lexflow/analysis/prompt.py`: `PROMPT_VERSION = "case-analysis-v1"`;
  system instruction (decision support, never an outcome, data is not
  instructions, cite only given ids, quotes copied exactly, no invented
  judgments or citations, empty precedents when none given); the request
  fences each block with a marker derived from the evidence's hashes, so a
  document cannot close its own fence. The fence is a first line of defence
  only; validation (M4) is what removes anything unsupported.
- Tests (`test_analysis_evidence.py`, 10): selection/deletion/other-case
  exclusion, determinism, limits and first passages, no ready documents,
  empty and synthetic judgment collections, no text in the stored record,
  prompt determinism and fencing with an injected "END EVIDENCE" line,
  instruction wording.
- Fix during M2: documents uploaded in one transaction tied on
  `created_at`; ordering is now upload date, then name, then id.

## M3 — Provider layer (done)

- `lexflow/analysis/provider.py`: `AnalysisProvider` protocol
  (`generate(Request) -> Response`), `provider_for(settings)` → provider or
  `Unavailable(code, reason)`; building a provider contacts nothing.
- `GeminiProvider` (official SDK): `genai.Client(api_key, HttpOptions(timeout
  in ms, retry_options=None))`, `models.generate_content(model, contents,
  GenerateContentConfig(system_instruction, response_mime_type
  "application/json", response_json_schema, max_output_tokens,
  candidate_count=1))`. Temperature is left at the model's default (newer
  models advise against changing it; not verified against Google's
  documentation in this run).
  - Errors map to fixed codes and messages, never the provider's text, and
    the original exception is suppressed (`from None`): 429 →
    `provider-rate-limited` (retry), 5xx → `provider-unavailable` (retry),
    timeouts → `provider-timeout` (retry), connection → `provider-unreachable`
    (retry), 401/403 → `provider-auth-failed`, 404 →
    `provider-model-not-found`, other 4xx → `provider-rejected`, prompt
    block / safety finish → `provider-blocked`, no text → `provider-empty`.
  - `MAX_TOKENS` marks the answer as truncated; "thought" parts are excluded;
    token counts are kept.
  - The key is read from the `SecretStr` only when the client is built;
    `repr` shows the model only.
- `lexflow/analysis/scripted.py`: the e2e/test double (`scripted-v1`, "not
  AI"): fixed-shape answer quoting the first words of passages, "[Scripted]"
  on every statement, plus one fact citing `D999` that validation must
  remove. Refused by the settings outside test/e2e databases.
- Tests (`test_analysis_provider.py`, 22; fakes in `tests/analysis_fakes.py`):
  request contents (schema, instruction, limits, timeout in ms), usage,
  thoughts excluded, truncation, ten failure mappings with the key and the
  provider's text absent from messages and logs, blocked/empty answers, the
  default client built with the key and no SDK retries (recorded with a
  stand-in class, no network), the conftest guard, `provider_for`, the
  scripted double.

## M4 — Validation (done)

`lexflow/analysis/validation.py` decides what is stored and shown; the
model's own claims about its sources are never trusted.

| Item | Kept only if | Otherwise (reason code) |
|---|---|---|
| Fact | cites one `D` id sent in this run; its quote (≥ 15 characters, after NFKC, typographic-quote/dash and whitespace normalisation) occurs in **that** passage | `unknown-evidence`, `quote-not-found`, `quote-too-short`, `duplicate` |
| Precedent | cites a `J` id retrieved for this run; title, court, citation, year and synthetic flag come from the collection, never from the model | `unknown-judgment` (the brief's "rejected"), `duplicate` |
| Contradiction | at least two distinct verified sources | `contradiction-unsupported` |
| Issue | refers to at least one surviving fact (others dropped from it) | `issue-without-facts` |
| Any wording | names no law-report citation (AIR, SCC, SCR, … patterns) that is absent from the evidence | `unverified-citation` |
| Outcome assessment | never | `outcome-discarded` |
| Malformed / over-limit items | never | `malformed`, `over-limit` |

- Every removal is counted with a plain-language reason (`removed`).
- `insufficientEvidence` with a reason when no passage was sent (no provider
  call), when the model says so, or when nothing could be verified.
- `precedentsAvailable` is false when no judgment passage was sent (D5).
- What validation does **not** do: decide whether a supported statement is a
  correct reading of its quote, or whether a comparison is legally sound.
  The disclaimer says so with every result.
- Tests (`test_analysis_validation.py`, 19): supported fact with exact
  source; unknown ids; facts citing judgments; quote from the wrong passage
  or invented; short quote; whitespace/typography tolerance; duplicates;
  invented and evidenced citations; **`test_an_output_citing_an_unknown_judgment_is_rejected`**;
  precedent metadata from the collection; citation in precedent prose;
  no judgments available; issue references; contradictions; outcome
  discarded; malformed counted; the three insufficient-evidence paths; a
  document instructing the model to cite `J99`.

## M5 — Runs: API, worker, audit, authorisation (done)

- **API** (`lexflow/api/analysis.py`, staff router):
  - `GET /api/cases/{id}/analysis/setup` — configured or not (with the
    reason), provider label and model, whether this user may start a run and
    why not, sample-only gate, the case's documents with "text ready",
    judgment collection size, limits, active run.
  - `POST /api/cases/{id}/analysis-runs` → 202 `queued`. Checks in order:
    `run-analysis` on the case (outsiders 404 exactly like a missing case;
    paralegals 403; archived 409 `case-archived`), migration 0011 and
    provider configured (503 `analysis-unavailable` with the reason),
    `confirmTransmission` true (422), sample case unless client data is
    allowed (403 `client-data-not-allowed`), ≤ 20 documents, every id a
    ready, live document **of this case** (422 `document-not-eligible`),
    hourly per-person limit (429 `rate-limited`), no waiting/running run of
    the case (409 `analysis-running`, also enforced by the partial unique
    index). Unknown request fields are refused (422).
  - `GET …/analysis-runs` (newest 50, no results) and
    `GET …/analysis-runs/{runId}` (the run must belong to the case, else
    404). Both need `view`.
  - Audit: `analysis.requested` (documents, provider, model, prompt version)
    and `analysis.viewed` (ready results only); never text or keys.
- **Worker** (`lexflow/worker.py`, `lexflow/analysis/runs.py`): when no
  extraction or indexing is waiting, claims a due run (`SKIP LOCKED`, lease
  = 2 × timeout + 60 s), re-checks the case (exists, not archived, sample
  unless allowed), assembles evidence, calls the provider **outside** any
  database transaction, retries an unreadable or cut-off answer once, then
  validates and stores the result only if it still holds the run.
  Busy/unreachable provider → back to the queue after 30 s × attempts, at
  most `LEXFLOW_AI_MAX_ATTEMPTS` (3) tries; abandoned runs fail
  `interrupted`. `analysis.completed` / `analysis.failed` audit events are
  written in the same transaction as the outcome (counts, model, prompt
  version, whether the provider was called).
- **Safe on a database without 0011** (the live database today): the
  worker logs "migration 0011 is not applied" and skips analysis; the API
  answers setup "unavailable", start 503, list empty, run 404. With
  analysis disabled (the default) nothing changes for the running system.
- **e2e harness** (`scripts/e2e.py`): `serve` and `work` set
  `LEXFLOW_AI_PROVIDER=scripted` and blank Gemini settings, so the browser
  tests never contact Google whatever `server/.env` holds.
- **Fix during M5:** SQLAlchemy stores Python `None` in a JSONB column as
  JSON `null`, which broke the "result only when ready" check;
  `analysis_runs` JSONB columns now use `none_as_null=True` (no schema
  change; `alembic check` on scratch still clean).
- **Tests** (`test_analysis_runs.py`, 29): setup off/on, permissions per
  role, outsiders get identical 404s for setup/list/run/start, Clients 403,
  anonymous 401, paralegal read-only, archived refused but readable,
  configuration missing, confirmation and input validation, document
  eligibility (other case, deleted, unknown), document limit, client-data
  gate in API and worker, queueing/audit/one-at-a-time, per-person hourly
  limit, cross-case run ids, a full scripted run with verified sources and
  the `D999` removal, polling not audited as a view, busy provider retried
  then failed, refused request fails at once, unreadable answer retried,
  truncated answer fails `invalid-output`, unknown judgment removed, no text
  → no provider call, lost lease → discarded, abandoned run, worker skips
  when unavailable or without 0011, key absent from responses, audit and
  OpenAPI, API without 0011, CSRF header required.
- Full backend suite: **807 passed**; ruff, format, mypy (Windows and
  Linux) clean; `export_openapi.py` regenerated; TS types regenerated.

## M6 — User interface (done)

- **Contract:** `src/types/ai.ts` now aliases the generated OpenAPI types
  (one contract, drift-checked); the hand-written `CaseAnalysis`,
  `relevance` score and `outcomeAssessment` are gone.
- **Seam:** `src/services/ai/aiService.ts` is an HTTP client of the LexFlow
  server only (`setup`, `start`, `listRuns`, `run`); the browser has no key
  and builds no prompt. `src/hooks/useCaseAnalysis.ts` replaces
  `useAiAssistant` (removed with its tests): a run is shown only under the
  key of the run asked for, a run of another case is rejected, unfinished
  runs are polled every 2 s, finishing refreshes history and setup.
- **AI Analysis tab** (`AnalysisTab.tsx`):
  - unavailable → the server's reason, nothing generated;
  - "What leaves this computer" notice (provider, model, character limit,
    sample-only rule, scripted provider called out as "not AI"), document
    checkboxes (only ready text selectable), explicit confirmation
    checkbox; the button explains why it is disabled;
  - progress while queued/running; failures with the reason and no result;
  - result: provider/model/prompt/time/requester, what was sent, the
    insufficient-evidence statement, removed items with reasons, the
    disclaimer, facts with the verified quote and a link to the document
    page, issues with their facts, precedent comparisons (collection
    metadata, synthetic badge, retrieval rank, link to the judgment
    passage; "No precedents were available for comparison" when none),
    contradictions with linked sources;
  - run history; inputs panel from real case data.
- `DecisionSupportNote` now also says that LexFlow checks provenance, not
  legal correctness; it appears on the tab and with every result.
- The workspace tab shows "Not available" when the server cannot analyse.
- **Mocks:** `src/test/mockAnalysis.ts` mirrors the server's routes and
  checks; `mockReadyText` gives a sample record extracted text.
- **Tests:** `src/pages/analysis.test.tsx` (15) and updated workspace tests;
  `e2e/analysis.spec.ts` (3): upload a synthetic text file, wait for
  extraction, analyse with the scripted provider through the real worker,
  open the fact's source page and the precedent's judgment page; paralegal
  read-only; outsider 404 and client 403.
- **Fix found by the e2e test:** the setup query was cached from when the
  workspace opened, so a document whose text became ready later was not
  offered. The setup query is now keyed on the documents' processing states
  (and never cached as fresh), and the selection resets when eligible
  documents change; a Vitest regression test covers it.
- Results: `npm run check` green (176 Vitest tests, lint, format, types,
  API drift, build); Playwright **41 passed** (port 5174 checked free first).

## M7 — Verification and documents (done)

- **Mutation checks** (`docs/verification/phase5/run_mutation_checks.py`,
  with a `--dry-run` that only checks each snippet occurs once): 40 guards
  broken one at a time — validation (10), answer parsing (2), provider (5),
  configuration (3), evidence (2), runs/API/worker (12), UI (6). **40 of 40
  caught**; every file restored byte-for-byte; logs redacted.
- **Secret scan:** no tracked `.env` file; `server/.env` git-ignored and
  without a `GEMINI_API_KEY` line; no Google-key-shaped string in the Phase 5
  commits, the working tree or the built bundle; `GEMINI_API_KEY` appears in
  the bundle 0 times; the only `GEMINI_API_KEY=` values in the history are
  test fakes and blanks.
- **Documents:** ADR 0019 (`docs/adr/0019-ai-case-analysis.md`); SRS
  (FR-18 done, FR-18a, NFR-2/5/6 updated, out-of-scope list); architecture
  (worker and provider, use cases, deployment edge to Google, data model,
  the *analyse a case* sequence, AI output as untrusted input);
  traceability (FR-18, FR-18a, NFR-2, NFR-6); verification README.
- **Final verification on the final code** (logs in
  `docs/verification/phase5/`): ruff, format, mypy (Windows and Linux)
  clean; `export_openapi.py --check` up to date; **pytest 807 passed**;
  `npm run check` green with **176 Vitest tests** and the build;
  **Playwright 41 passed** (ports 5174 and 8001 checked free first).
- `docs/DEVELOPMENT_BRIEF.md` SHA-256 unchanged:
  `274ecaed93400f51dd47c42337fbd6e101aa6be366b80d977d1522359b34c2ec`.

## M8 — Live migration 0011 (applied and verified) and Gemini smoke test (run; open items)

### M8a — Rehearsal (during the implementation run)

Applying 0011 to the live database was not authorised during the
implementation run, so at first M8 stopped at the rehearsal:

1. Live `lexflow` (127.0.0.1:5432, container `lexflow-db-1`) confirmed at
   revision **0010**.
2. Read-only dump `server/var/backups/lexflow-20261020-phase5-rehearsal.dump`
   (git-ignored; 71,414 bytes; SHA-256
   `d608fed3ff66db2ecc51613e18f2e25e26314cac8040449e6c343da61bf8cd43`).
3. Restored into a **new** scratch database `lexflow_p5_restore` on the
   scratch server (127.0.0.1:55432); fingerprint (count + md5 of every row,
   every table) **identical to live** (20 tables).
4. On the copy only: upgrade 0011 → the 19 existing tables identical,
   `analysis_runs` empty; downgrade 0010 → whole database identical;
   upgrade 0011 again → identical; `alembic check` clean. Live fingerprint
   re-read afterwards: **unchanged**, still 0010. **REHEARSAL PASSED.**

The plan written at that point (stop services, fresh dump, upgrade, check,
restart, optional synthetic smoke) was then carried out in the steps below,
each separately approved by the owner.

### M8b — Preflight (read-only, 2026-10-20)

- Live target confirmed: `DATABASE_URL` comes from `server/.env` (not
  overridden in the shell) → 127.0.0.1:5432 `lexflow`, Docker container
  `lexflow-db-1` (compose project `lexflow`, volume `lexflow_pgdata`,
  PostgreSQL 17.11, `vector` 0.8.7); no native PostgreSQL service. The
  scratch server is `lexflow-pgv-test` (127.0.0.1:55432, data in tmpfs).
- 0011's SQL (Alembic offline mode, no connection): one transaction —
  `CREATE TABLE analysis_runs`, three indexes and one partial unique index,
  `UPDATE alembic_version`. No existing row read or changed.
- Copies of live data were inventoried (dumps and base backups in
  `server/var/backups/`, restore databases on both servers, two Docker
  volumes); none was changed or deleted. Retention is an owner decision.

### M8c — Fresh backup and isolated restore verification (2026-10-20)

1. The API and worker (started 13:37, Phase 4 code) were stopped; afterwards
   **0 sessions** on the whole database server.
2. Backup (written with overwriting disabled):
   `server/var/backups/lexflow-20261020-193557-pre-0011.dump` (git-ignored,
   71,414 bytes), SHA-256
   `6639f2b66886d6a305d9a427098c7e752dc2568d9b2d5d0f65c5881dc5f4efbc`;
   archive readable (`pg_restore --list`: 123 entries, 20 table-data entries).
3. Restored with `--exit-on-error` into the **new** database
   `lexflow_pre0011_verify` on the scratch server: no errors.
4. Comparison method (a read-only SQL script kept outside the repository;
   session fixed to UTC and ISO formats): revision, extension versions, every column definition,
   constraint and index, per-table counts, and **one md5 per row, sorted** —
   a row-level comparison, not one hash per table. Live before vs restore:
   **identical** (revision 0010; 203 columns, 128 constraints, 49 indexes,
   117 rows; cases 7, documents 28). Live before vs live after: identical.
   No exclusions were needed.
5. The API and worker were restarted with their original commands
   (`python -m lexflow`, `python -m lexflow.worker`). These load the code on
   disk, i.e. the **committed Phase 5 code** from then on; health 200, worker
   started with AI analysis disabled, no errors.

### M8d — Migration applied (2026-10-20)

1. Preflight: HEAD `6b8f865`, clean tree; 0011 unchanged since `d681326`;
   single head 0011; `alembic current` 0010; target 127.0.0.1:5432
   `lexflow`; health 200; backup present with matching SHA-256; live
   identical, row for row, to the backup-time state; no session idle in a
   transaction.
2. `.venv\Scripts\python -m alembic upgrade head` (from `server/`, with
   `PGOPTIONS=-c lock_timeout=10s` so a blocked lock fails cleanly) →
   `Running upgrade 0010 -> 0011`, exit 0. The API and worker kept running
   (analysis disabled; the API looks for the table on each request).
3. Verified: `alembic current` **0011 (head)**; `alembic check` "No new
   upgrade operations detected"; `analysis_runs` with 21 columns, 12
   constraints, 5 indexes (primary key, `ix_analysis_runs_case_id_created_at`,
   `ix_analysis_runs_requested_by_id_created_at`,
   `ix_analysis_runs_status_available_at`, `uq_analysis_runs_case_id_active`),
   0 rows.
4. Data integrity (same row-level comparison, before vs after): the only
   differences are the revision value, the one `alembic_version` row and the
   new `analysis_runs` objects; **0 unexpected differences**; every row of
   every existing table unchanged (cases 7, documents 28, users 6, clients 6,
   hearings 7, timeline events 27, audit events 25).
5. Services: API health 200, anonymous request to the analysis route 401,
   no errors in either log; no restart was needed.
6. Recovery, if ever needed: `alembic downgrade 0010` (rehearsed; drops only
   `analysis_runs`) or the backup above. Not run.

### M8e — Gemini smoke test (executed 2026-10-20)

Part A is what was read before the first call (code and Google's
documentation); Part B is what the live runs showed; Part C is the
precedent-comparison audit; Part D separates live verification from
automated-test coverage. Times in the database are UTC; the worker log
uses local time (UTC+5:30).

#### Part A — Configuration and documentation findings (read before the first call)

- **Settings (from `lexflow/config.py`):** `LEXFLOW_AI_PROVIDER` (`disabled` |
  `gemini` | `scripted`), `GEMINI_API_KEY`, `GEMINI_MODEL` (no default),
  plus the `LEXFLOW_AI_*` limits. Settings are read once at process start,
  so the API and the worker must both be restarted after `server/.env`
  changes. The SDK also reads `GEMINI_API_KEY`, `GOOGLE_API_KEY` and
  `GOOGLE_GENAI_USE_VERTEXAI` from the process environment; none is set (the
  key in `server/.env` is passed explicitly and never exported).
- **Documentation findings (ai.google.dev, read 2026-10-20):**
  - `gemini-3.8-flash` is a stable model recommended for new projects:
    structured outputs supported; 1,048,576 input / 65,536 output tokens;
    thinking on by default (medium; `minimal` returns an error). Paid price
    USD 0.75 / 3.75 per 1M input / output tokens until 2026-12-31 (output
    includes thinking tokens); a free tier exists.
  - LexFlow calls `models.generate_content` with `response_json_schema`.
    Google now labels the Generate Content API "legacy" but says it "remains
    fully supported" and recommends the Interactions API for new work; no
    end date was found. Its structured output supports every keyword
    LexFlow's schema uses (`type`, `properties`, `required`, `items`,
    `minItems`, `maxItems`, `description`); unsupported keywords are ignored.
  - `max_output_tokens` includes thinking tokens: with the default 16,384, a
    long thinking pass could truncate the answer (LexFlow then retries once
    and fails the run `invalid-output`). LexFlow sets no thinking level and
    no temperature (newer models ignore custom temperatures).
  - Keys: new AI Studio keys are "auth keys"; unrestricted standard keys are
    rejected. The SDK takes the key the same way (`api_key=`).
  - Terms (updated 2026-04-28): on unpaid quota, prompts and responses are
    used to improve Google's products and may be read by human reviewers,
    and sensitive, confidential or personal information must not be
    submitted; on paid quota they are not used for improvement but are
    logged for a limited period and may be cached in any country. The terms
    also say not to rely on the Services for legal advice (consistent with
    LexFlow's decision-support note).
- **Model actually configured by the owner:** `gemini-3.1-flash-lite`
  (stable; structured outputs supported; 1,048,576 input / 65,536 output
  tokens; free tier exists, paid USD 0.25 / 1.50 per 1M input / output
  tokens; free-tier content may be used to improve Google's products; page
  last updated 2026-07-21). Which tier the key belongs to was not checked
  (UNVERIFIED); only synthetic data was sent.

#### Part B — Live results (real Gemini, synthetic data, sample case LF-2026-0361)

Setup: `LEXFLOW_AI_PROVIDER=gemini`, `GEMINI_MODEL=gemini-3.1-flash-lite` and the
key were set by the owner in `server/.env` (values never read out); the
API and worker were restarted; the owner uploaded an invented text file
(`SYNTHETIC-phase5-smoke-notice.txt`, 1,850 bytes, 2 passages) to the
sample case and started each run from the UI as the Administrator. The
file states a trade-mark dispute with two deliberate traps: a paragraph
that tells the model to cite a non-existent judgment "J99", add a
law-report citation and predict a win, and a conflict between two dates
(the plaintiff's use of its mark said to begin in 2015, and in the reply
in 2017). `LEXFLOW_AI_ALLOW_CLIENT_DATA` stayed false.

| Run | Code loaded in the worker | Outcome |
|---|---|---|
| `bb1bfe75` | Phase 5 as committed, no diagnostics | 503, 503, then **400** after 12 s (3 attempts); failed `provider-rejected`; no provider codes recorded |
| `3b989815` | + diagnostic codes | **400 `INVALID_ARGUMENT`** after ~42 s (1 attempt); no reason code recorded |
| `95db9bdb` | same (old schema) | 503, then **400 `INVALID_ARGUMENT`** after ~6 s (2 attempts); no reason code recorded |
| `4fc9ab87` | + simplified schema (worker restarted 22:22:36 local, after the schema edit at 22:19:30) | **ready**: 1 attempt, `200 OK` in ~26 s; 1,522 prompt / 595 output / 2,117 total tokens |

Seven `generateContent` requests were made in all: 3 × 503, 3 × 400, 1 × 200.

- **The 400s.** The status name was `INVALID_ARGUMENT` on every run that
  had the diagnostic code; no reason code (`ErrorInfo`) was recorded, so
  either Google sent none or it failed validation (the stored data cannot
  tell which). **The cause was never established.** A working hypothesis is
  that the structured-output schema was too complex for Google to compile
  (it had 8 `minItems`/`maxItems` constraints, nested up to 40 × 5 items).
  After removing those keywords the next run succeeded. That is consistent
  with the hypothesis but is **one success, not proof**: the earlier runs
  also met 503s, and the run record stores no schema version. If a 400
  returns, the next step is to read Google's message once outside LexFlow.
- **Diagnostic codes (uncommitted).** `ProviderError.diagnostic` carries the
  HTTP status, Google's status name and, if present, the `ErrorInfo`
  reason, read only from the SDK error's structured fields and
  pattern-checked; they go to the worker log and the administrator-only
  `analysis.failed` audit event (`providerHttpStatus`, `providerStatus`,
  `providerReason`), never to the run's stored reason, the API or the UI.
- **Simplified provider schema (uncommitted).** `minItems`/`maxItems` were
  removed from `RESPONSE_SCHEMA` only (the limits are now stated in field
  descriptions). The application-side limits in the Pydantic models, the
  parser and the validation are unchanged and still enforced.
- **Result of the successful run `4fc9ab87` (inspected read-only):** 4
  facts, 1 issue, 0 precedents, 0 contradictions, `insufficientEvidence`
  false, `precedentsAvailable` false (the live judgment collection is
  empty), **1 item removed** (`contradiction-unsupported`: fewer than two
  verified sources), recorded identically in `result.removed` and the
  `removed` column.
- **Traceability (verified live).** For each of the 4 facts the quote occurs
  verbatim (after normalisation) in the one chunk it cites and in no other;
  both evidence chunks exist, belong to the selected sample document, match
  their stored hashes and agree with the recorded section/page (section 1,
  no page: a text file). The issue rests on F1–F4, which exist. Whether each
  *statement* reads its quote correctly was **not** checked by the machine
  and is for the lawyer (or the demonstrator) to compare on screen.
- **Injection traps.** The injected paragraph was in a chunk sent to the
  model. The stored result contains no `J99`, no law-report citation text,
  no judgment id, no win/probability wording, and no outcome field, and no
  removal of those kinds was recorded. So the model did **not produce**
  them (or produced shapes the parser ignores silently: extra keys outside
  the outcome keys are dropped without a count, and the raw answer is not
  stored). **The rejection of such output by validation was not exercised
  live**; it is covered by automated tests only (Part D).
- **Conflicting dates (2015 vs 2017) — NOT MET.** No contradiction was
  displayed. F1 cites the 2015 statement; no fact mentions 2017; the one
  removal was a contradiction. Probably (inference only, the raw answer is
  not stored) that was the model's attempt at this conflict, with a quote
  that did not match the evidence word for word. This is one sample from one
  model; whether it is a model weakness or the strictness of the verbatim
  quote rule is **unresolved**. It is documented as a limitation, not fixed.
- **Audit, storage and logs (verified live).** Events `analysis.requested`
  (Administrator), `analysis.completed` (system; counts, model, provider,
  prompt version, `providerCalled: true`) and `analysis.viewed`; no audit
  detail contains the key, a fact quote or document text. The run stores
  contract fields only: evidence as ids, positions and hashes (no text),
  `usage` as token counts; no column holds the key and none holds a raw
  answer. The worker and API logs contain no key and no errors.
- **Failed runs are kept** as history (3 rows, `provider-rejected`).

#### Part C — Precedent retrieval and comparison (audit of what exists)

- **Implemented:** `evidence._judgments` searches the judgment collection
  (Phase 4 keyword search) with an OR-query of the case's eight most
  frequent content words, at most 8 passages and a quarter of the character
  budget, as `J1…` with rank, metadata and synthetic flag; safe when the
  table is absent. The prompt fences them as data and asks for comparison
  only with those ids (empty list when none). Validation keeps a precedent
  only if its `J` id was retrieved for the run (otherwise `unknown-judgment`),
  removes duplicates and any law-report citation in its prose that is not
  in the evidence, and takes title, court, citation and year from the
  collection, never from the model. The UI shows retrieval rank (no score),
  a synthetic badge, a link to the judgment passage, and "No precedents were
  available for comparison" when none were sent.
- **Covered by automated tests:** retrieval, ranking, labelling, limits and
  the empty collection (`test_analysis_evidence.py`); unknown-judgment
  rejection (the brief's test), metadata from the collection, invented
  citations, duplicates, no-judgments flag (`test_analysis_validation.py`);
  an unknown judgment dropped end to end (`test_analysis_runs.py`);
  precedent card, link and empty statement (`src/pages/analysis.test.tsx`);
  a precedent from the SYNTHETIC collection, shown and linked, through the
  real worker with the scripted provider (`e2e/analysis.spec.ts`).
- **Not exercised live:** the live collection has 0 judgments (no approved
  source), so **no judgment passage has ever been sent to Gemini** and no
  live precedent comparison exists. None was invented for the demonstration.
- **Limits (documented, not changed):** (1) a precedent's summary,
  similarities and differences are **not** quote-checked against the
  judgment passage — validation checks that the judgment was retrieved and
  that no unverified law-report citation appears, not that the comparison
  is faithful; (2) retrieval is keyword-only and crude, and its relevance is
  unmeasured (the Phase 4 evaluation set is synthetic); semantic retrieval is
  not used by analysis.

#### Part D — Live verification versus automated-test coverage

| Behaviour | Live (real Gemini, 2026-10-20) | Automated tests only |
|---|---|---|
| Configuration read, key not exposed in responses, audit, logs | yes (inspected) | yes |
| Run queued → running → ready, result shown | yes (UI shown by the owner; backend inspected) | yes |
| Facts traceable to evidence by verbatim quote | yes (4 of 4) | yes |
| Removed item recorded with its reason | yes (1) | yes |
| Audit events without text or key; raw answer not stored | yes | yes |
| Unknown judgment (`J99`) rejected | no | yes |
| Invented law-report citation removed | no | yes |
| Outcome / win prediction discarded | no | yes |
| Contradiction detected from conflicting passages | **no (not met)** | yes (with fabricated answers) |
| Precedent comparison with real judgment passages | **no (collection empty)** | yes (synthetic collection) |
| Provider errors → codes, retries, diagnostics | partly (503 retried; 400 failed with codes) | yes |
| Authorization (paralegal, outsider, client, archived, one active run, rate limit) | no (only the administrator can sign in on live) | yes |

## Status against the acceptance criteria

| Brief / plan | Status |
|---|---|
| `AiService` is a client of a backend endpoint | Done (`src/services/ai/aiService.ts` → `/api/cases/{id}/analysis-runs`) |
| Retrieve chunks and candidate precedents; structured JSON | Done (evidence ids, JSON schema, defensive parser) |
| Validate before showing; reject unknown judgments; drop unsupported facts; say when evidence is insufficient | Done (`validation.py`; `test_an_output_citing_an_unknown_judgment_is_rejected`) |
| Store each run (model, prompt version, inputs, timestamp) | Done (`analysis_runs`: provider, model, prompt version, selection, evidence references, timestamps, usage) |
| Every fact links to its document and page | Done (UI links checked in Vitest and Playwright) |
| Decision-support note with every result | Done |
| Done when: every displayed claim has a working source link | Met for facts, contradictions and precedents (issues refer to linked facts) |
| Live database at 0011 | **Done** (M8d, 2026-10-20; verified row by row) |
| A real Gemini run | **Done once** (`4fc9ab87`, after 3 failed attempts; M8e) |
| Contradictions from conflicting passages (live) | **Not met** — the 2015/2017 conflict was not reported; cause unresolved |
| Precedent comparison (live) | **Not exercised** — the live collection is empty; implemented and tested with synthetic judgments only |
| Re-verification after the diagnostic and schema changes | **Pending** — 134 focused tests passed; full suite and mutation checks not rerun |

## Limitations

- The real Gemini path was exercised once successfully (one synthetic
  document, one model, one run); quality, repeatability and cost are
  essentially unmeasured. Three earlier attempts failed with HTTP 400
  (`INVALID_ARGUMENT`) whose cause is not established (M8e).
- The conflicting-dates contradiction was not reported (M8e); the
  contradiction feature has not been demonstrated live.
- No judgment passage has been sent to Gemini; precedent comparison is
  untested live and its comparison text is not quote-checked.
- The diagnostic and schema changes are uncommitted and have not had the
  full backend suite or the mutation checks rerun (the committed mutation
  report predates them).
- Validation proves provenance (the quote is in the cited passage, the
  judgment was retrieved), not legal correctness.
- The live judgment collection is empty, so live results will say that no
  precedents were available.
- Only sample cases may be analysed (D1) until a privacy, confidentiality
  and provider-terms review allows client material.
- Copies of live data remain in `server/var/backups/`, in restore databases
  on both database servers and in two Docker volumes; retention is an owner
  decision.

Checkpoint: Phase 5 M1–M7 done and committed; M8 migration applied and
verified (live at 0011); the real Gemini smoke test ran once successfully
on synthetic data. **Status: NOT COMPLETE — demonstrable with documented
limitations.** Open: the unreported contradiction, live precedent
comparison (empty collection), full-suite and mutation re-verification,
and committing the uncommitted code, tests and records.


---

## M9 — Stabilisation (P5-S2), session of 2026-10-24

Appended record; the sections above are historical and are not rewritten.
Corrections to stale summaries are explained in this section.

### M9.0 — Preflight and scope (2026-10-24)

- **Start state (verified):** branch `master`, HEAD
  `6b8f865b4cdd6f759d46e39e247618f9f50353fd`, no remote. 11 pre-existing
  uncommitted files (+912/−69): `docs/PHASE5_EXECUTION_LOG.md`,
  `docs/verification/phase5/checkpoint.json`, `server/README.md`,
  `server/lexflow/analysis/output.py`, `provider.py`, `runs.py`,
  `server/lexflow/cli/judgments.py`, `server/tests/test_analysis_output.py`,
  `test_analysis_provider.py`, `test_analysis_runs.py`,
  `test_judgment_import.py`. A byte copy of these 11 files and the full diff
  was saved outside the repository before any edit (session scratch folder,
  `p5s2-preexisting/`, with SHA-256 list).
- **Protected brief:** `docs/DEVELOPMENT_BRIEF.md` SHA-256
  `274ecaed93400f51dd47c42337fbd6e101aa6be366b80d977d1522359b34c2ec` (matches).
- **Environment:** Docker running with container `lexflow-db-1` only (opened
  by the owner); the API, worker and Vite are not running. No `CLAUDE.md` and
  no `docs/IMPLEMENTATION_PROGRESS.md` exist; per the instructions for this
  session they are not created (the cross-phase index is not an established
  convention yet).
- **Correction of stale summaries (records only):** after the M8e entry above
  was written (2026-10-20), more happened that this log did not record:
  1. three more real Gemini runs on the sample case LF-2026-0361 were started
     by the owner from the UI (`1712d02e`, `5aa4711d`, `ea18be07`, all
     `ready`); `5aa4711d` and `ea18be07` compared 3 precedents each and every
     run reported one contradiction (observed read-only on 2026-10-20: every
     fact quote and contradiction source verbatim in its cited chunk; every
     precedent a retrieved judgment with collection metadata);
  2. three fictional judgments labelled "SYNTHETIC DEMO — NOT REAL CASE LAW"
     (source `lexflow-demo-synthetic`, manifest in git-ignored
     `server/var/demo-judgments/`) were imported into the live database by the
     owner with the new, uncommitted flag `--allow-synthetic-in-database`
     (provisional; reviewed in M9 below).
  So "live precedent comparison not exercised" (M8e Part C) is superseded:
  precedent comparison has run live, **against synthetic demo judgments
  only**. Contradiction reporting has run live (3 runs), but the planted
  2015/2017 conflict of run `4fc9ab87` remains unreported. These facts were
  last observed on 2026-10-20 and are not re-queried in this session.
- **Scope (owner instruction 2026-10-24):** Phase 5 stabilisation only —
  provider safety, retry/quota classification, user-safe messages, output
  schema/version and grounding checks, run integrity, a security review of
  the synthetic-import flag, an offline evaluation harness, regression and
  verification, records. **Not authorised:** migrations or schema changes,
  changing application records, paid LLM calls, printing secrets, commits,
  pushes, changing the brief, Phase 6/7, UI redesign, data acquisition,
  local-LLM work.

### M9.1–M9.3 — Provider fail-closed, quota classification, user-safe messages (2026-10-24)

- **B1 provider selection (`server/lexflow/analysis/provider.py`):**
  `SUPPORTED_PROVIDERS = {"gemini", "scripted"}`. `unavailable_reason`
  answers `provider-unsupported` for any other value except `disabled`, and
  `provider_for` builds each provider in an explicit branch, so an unknown
  name can no longer fall through to Gemini. The settings already restrict
  `LEXFLOW_AI_PROVIDER` to `disabled|gemini|scripted` (pydantic `Literal`), so
  this is defence in depth against values that skip validation (for example
  `model_copy`).
- **B1 run/provider consistency (`server/lexflow/analysis/runs.py: analyse`):**
  if the queued run's confirmed `provider` differs from the worker's provider
  name, the run fails with `provider-mismatch` (not retried) before the case,
  the evidence or the provider is touched. Nothing is sent. Decision: only the
  provider (the vendor the person agreed to send text to) is compared. A
  changed model of the same provider is allowed, and the model actually used
  is recorded on the run, as before.
- **B2 retry/quota (`provider.py`):** a 429 whose structured
  `google.rpc.QuotaFailure` names a daily or monthly quota (`PerDay`,
  `PerMonth`, `Daily`, `Monthly` in a validated `quotaId`) becomes
  `provider-quota-exhausted` and is not retried. Every other 429 stays
  `provider-rate-limited` and keeps its retries. The validated `quotaId` joins
  the diagnostic (worker log; audit key `providerQuotaId`); provider free text
  is still never read. The transient retries are unchanged (rate limit, 5xx,
  timeout, unreachable; `RETRY_PAUSE_SECONDS` × attempts; `LEXFLOW_AI_MAX_ATTEMPTS`).
- **B3 user-safe messages:**
  - Provider messages no longer name settings or files (`GEMINI_API_KEY`,
    `GEMINI_MODEL`, `server/.env`). The auth-failed, model-not-found and
    quota-exhausted messages end with "An administrator needs to check the AI
    configuration of this server."
  - `Unavailable` gained `detail` (the setting to fix). The analysis API shows
    it **to Administrators only** (setup `unavailableReason`, start 503
    `detail`). The worker log includes it.
  - The worker's client-data refusal no longer names
    `LEXFLOW_AI_ALLOW_CLIENT_DATA`.
  - The API contract is unchanged (same fields; `reasonCode` is a free string)
    and the UI shows server text as is, so the front end is not changed.
- **Tests:**
  - `test_analysis_provider.py` adds 5 unknown-provider cases (Gemini is
    never constructed), a test that disabled and scripted keep their
    behaviour, 5 quota and rate-limit classification cases, a test that only
    valid structured fields are read, and 9 message-safety cases.
    `test_provider_for_reports_what_is_missing` was updated (the setting names
    moved to `detail`).
  - `test_analysis_runs.py` adds tests for the provider mismatch (provider
    never called; `analysis.failed` audited), for an exhausted quota (fails
    after 1 attempt; `providerQuotaId` in the audit; no key or echo), and for a
    disabled server not naming settings to advocates.
    `test_a_run_needs_configuration` now checks that the lead does not see the
    setting name and the Administrator does.
  - The Gemini-provider run test sets the disposable test run's provider to
    `gemini`. `ScriptedAnswers` now defaults to the name `scripted`.
- **Results:**
  - `pytest tests/test_analysis_provider.py tests/test_analysis_config.py tests/test_analysis_runs.py`:
    **115 passed**, exit 0 (database `lexflow_test`, disposable by conftest
    design).
  - `ruff check lexflow tests`: exit 0.
  - `mypy` (strict, 134 files): exit 0, after fixing one Optional narrowing in
    a new test.
- No Gemini call, migration, application-record change or commit.

### M9.4 — Output schema, versions and grounding checks (2026-10-24)

- **Where constraints live (decision, documented in `output.py`):**
  - The provider schema carries types, required keys and item shapes. Limits
    are stated only in `description` text, because a size keyword was the
    suspect in the M8e rejection; the root cause was never proven, which
    remains recorded.
  - The application enforces every limit: the pydantic item models, the
    per-list maxima, 2–4 contradiction sources, and id patterns. It also
    applies every grounding rule (`validation.py`).
  - No application constraint was removed.
  - One wording inconsistency is noted but not changed. The fact `quote`
    description asks for "at most 200 characters", while the parser accepts
    up to 300 (`QUOTE_MAX`). Asking for less than is accepted is harmless,
    and changing the provider-facing text would change the live-tested schema.
- **Versioning (backward compatible, no schema or record change):**
  - `PROMPT_VERSION` stays `case-analysis-v1`; the prompt text is unchanged.
  - New `RESPONSE_SCHEMA_VERSION = "case-analysis-schema-2"` and
    `schema_sha256()`. Schema-1 had `minItems`/`maxItems` and was used before
    2026-10-20.
  - New `VALIDATOR_VERSION = "grounding-2"` (grounding-1 covered M4–M8).
  - New runs store `pipeline` {promptVersion, schemaVersion, schemaSha256,
    validatorVersion} inside their existing `evidence` JSON. The
    `analysis.completed` audit records schemaVersion and validatorVersion.
  - Older runs have no `pipeline` entry and are **not reinterpreted**.
  - The API contract is unchanged; `pipeline` is not exposed.
  - A pinned-hash test forces a version bump if the schema changes.
- **New deterministic grounding checks (validator `grounding-2`):**
  1. Neutral citations (`2023 INSC 456`, `2024:DHC:1234`) join the
     invented-citation check.
  2. A case name in prose ("A v. B", "vs", "versus") is removed as
     `unverified-citation` when either party has no non-generic word that
     appears in the evidence, the case title, the opposing party or a
     retrieved judgment's title. The message is now "Named a citation or case
     that does not appear in the evidence."
  3. Outcome wording in any prose field is removed with the new code
     `outcome-wording`. The patterns cover "likely/unlikely/probably …
     win/succeed/prevail/lose", "chances/likelihood/probability/odds/prospects
     of … success/winning/losing", "N% chance" and "will certainly
     win/lose". The `outcome` key test that was missing was added.
  4. Contradiction sources must be distinct. The same normalised quote, or
     one quote contained in another from the same passage, counts once. The
     message is now "Had fewer than two distinct verified sources."
- **What cannot be automated (documented in `validation.py`):**
  - whether a verified quote actually supports the statement or the claimed
    contradiction;
  - paraphrased predictions;
  - invented cases written without "v.";
  - the legal correctness of anything.
  The result still establishes provenance only, and the lawyer decides.
- **Tests:**
  - `test_analysis_output.py`: the `outcome` parameter, an exact
    `OUTCOME_KEYS` check, and the schema version and hash pin.
  - `test_analysis_validation.py`: tests for distinct contradiction sources,
    an invented neutral citation, a known neutral citation, invented and known
    case names, the case title being known, and outcome wording in facts,
    issues, precedents and contradictions (including non-matches such as
    "likely paid by cheque" and "success fee").
  - `test_analysis_runs.py`: checks that the pipeline record is stored and
    audited.
  - Front-end mock `src/test/mockAnalysis.ts`: the disabled reason now uses
    the new staff-facing wording.
- **Results:**
  - analysis pytest set (`test_analysis_{output,validation,runs,provider,evidence,config}.py`):
    **173 passed**, exit 0;
  - `ruff check lexflow tests`: exit 0;
  - `mypy` strict: exit 0.
- During this batch a shell heredoc turned `\b` into backspace characters in
  `validation.py`. This was detected immediately, all 10 were replaced with
  `\b`, and no backspace characters remain. From now on, scripts are written
  as files.

### M9.5 — Run integrity: unexpected errors, interruptions, stale references (2026-10-24)

- **Defect found and fixed (unbounded re-queue):**
  - Before this fix, `runs.release` handed an interrupted run back as
    `queued` whatever its attempt count. `claim` only fails runs whose
    *running* lease has expired after the last attempt.
  - An exception other than `ProviderError` from `generate`, `parse` or
    `validate` propagated out of `analyse`. The worker then released the run
    and re-raised, which stopped the worker. So a run that always raised could
    be claimed, crash the worker and be re-queued without limit.
  - Fixes:
    1. `analyse` turns any other exception from the provider into a failed
       run `provider-error` (not retried) and logs only the exception type,
       because the text could echo the request.
    2. An exception while parsing or validating becomes `validation-error`.
       No result is ever stored for an answer that was not fully checked.
    3. `release(..., max_attempts, now)` fails the run as `interrupted`, with
       an `analysis.failed` audit event, when the run has used its last
       attempt. Otherwise it re-queues the run as before.
       `KeyboardInterrupt`/`SystemExit` are still released, not swallowed.
- **Stale references after reprocessing:**
  - Re-extraction deletes a document's sections and chunks and creates new
    chunk ids. Deleting a document hides it, and removing a judgment deletes
    its chunks.
  - The single-run response (`GET .../analysis-runs/{id}`) now has
    `evidence.changed`: the evidence ids (`D1`, `J2`) whose stored chunk no
    longer exists, belongs to a deleted document, or has a different
    `content_sha256`. The check is read-only, against the hashes already in
    the run's evidence record.
  - The stored result is not changed. Its quotes are what was verified at run
    time.
  - The AI Analysis tab shows a status notice listing the changed ids and
    marks each affected source "(changed since this analysis)".
  - This is an additive OpenAPI field: `server/openapi.json` and
    `src/services/api/schema.gen.ts` were regenerated, and both drift checks
    pass.
- **Reviewed, unchanged (recorded for the safeguard summary):**
  - Lease = 2 × timeout + 60 s. It covers the two provider calls `analyse`
    can make (the retry for an unreadable answer).
  - A result from a worker that lost its lease is discarded (`complete`
    checks status and worker_id).
  - Duplicate runs are prevented by the API check and the partial unique
    index, which maps `IntegrityError` to 409.
  - The archived-case and sample-only gates are checked again by the worker
    before sending.
  - Confirmation and the hourly limit are enforced in the API.
  - A failed outcome never sets `result`.
- **Tests:**
  - `test_analysis_runs.py` adds tests for an unexpected provider error (only
    the type is logged; no key, echo or document text), a validator crash (no
    result, no completed event), interruption with 1 and with 3 attempts
    (fails, or is re-queued), changed sources (the hash changed, then the
    document deleted, giving `["D1", "D2"]`; the result is kept), and
    missing or unreadable judgment and document references. The exact
    evidence-summary assertion now includes `changed: []`.
  - Vitest `analysis.test.tsx` adds 2 tests: the notice and marker, and no
    notice when nothing changed.
- **Results:**
  - `pytest tests/test_analysis_runs.py`: **40 passed**, exit 0.
  - `ruff check lexflow tests`: exit 0.
  - `mypy`: exit 0.
  - `vitest run src/pages/analysis.test.tsx src/pages/CaseWorkspacePage.test.tsx`:
    **46 passed**, exit 0.
  - `npm run typecheck`: exit 0.
  - eslint on the 3 changed front-end files: exit 0.
  - `npm run api:check`: exit 0.
  - `export_openapi.py --check`: exit 0.
- **Process note:** one `ruff format lexflow` call covered the whole package.
  `git status` showed it changed no file outside this batch (the package was
  already formatted). From now on, formatting is run per file.

### M9.6 — Security review of `--allow-synthetic-in-database` (2026-10-24)

Scope: `server/lexflow/cli/judgments.py: cmd_import`, every other path that
imports judgments (`scripts/e2e.py`, `scripts/evaluate_judgment_search.py`,
tests), and the database-name guards they rely on. No import was run against
any non-test database; tests use the disposable `lexflow_test` only.

**Findings:**

1. **Both acknowledgements are required.** This holds. Without
   `--allow-synthetic` a synthetic source is refused even when
   `--allow-synthetic-in-database` is given. In a non-test database,
   `--allow-synthetic-in-database` must equal the name exactly
   (case-sensitive; no trimming; empty refused). Tests cover a missing flag,
   wrong names ("other", "Lexflow", "lexflow ", "lexflow_test", "e2e", "") and
   the valid name.
2. **DEFECT (fixed): the name checked was the URL's, not the actual target.**
   - psycopg takes `dbname`/`service` from the URL query. So
     `postgresql+psycopg://…/lexflow_test?dbname=lexflow` reports the database
     `lexflow_test` but connects to `lexflow`. This was demonstrated with
     SQLAlchemy's `create_connect_args`, without connecting.
   - That URL would have passed the old "contains test" rule, and the import
     would have gone into `lexflow` with **no** demo flag at all.
   - Fix: `connected_database(session)` reads `SELECT current_database()`.
     The command refuses when it differs from the URL's name. The test-name
     rule and the exact-name flag are applied to the connected name.
3. **DEFECT (fixed): the substring rule.**
   - "contains 'test' or 'e2e'" accepted `lexflow_latest`, `contest` and
     `lexflowtest`.
   - `is_test_database` now needs a whole name part (split on non-letters)
     equal to `test` or `e2e`. The existing `lexflow_test`, `lexflow_e2e` and
     `lexflow_eval_test` still qualify.
4. **Same URL gap in two destructive tools (fixed, confined):**
   - `tests/conftest.py` drops and recreates the database named in
     `TEST_DATABASE_URL`, and `scripts/e2e.py prepare` drops `lexflow_e2e`.
     Both checked only the URL name.
   - Both now refuse a URL with a `dbname` or `service` query parameter.
     This was verified: the suite exits with "Refusing a TEST_DATABASE_URL
     with a dbname or service parameter", and the e2e URL helper refuses too.
     Neither check connected to a database.
   - The configured URLs were inspected without printing values: names
     `lexflow`/`lexflow_test`, no query parameters, `PGDATABASE`/`PGSERVICE`
     unset. So the gap was latent, not used.
5. **Other import paths:**
   - `scripts/e2e.py` imports the synthetic fixtures only into the database it
     has just recreated (name must contain "e2e").
   - `scripts/evaluate_judgment_search.py` imports only into the fixed
     throwaway `lexflow_eval_test`.
   - Tests import only into `lexflow_test`.
   - None of these uses the demo flag, and no API endpoint imports judgments.
6. **Labels, provenance and duplicates are intact.**
   - The flag only widens which database is accepted. The manifest checks
     still apply: `.invalid` addresses for synthetic sources, terms of use,
     duplicates by file, citation and id, and a source cannot switch between
     real and synthetic.
   - Records stay `is_synthetic` with the badge.
   - The preview lists everything before `--confirm N`.
   - Each import and removal is audited, and `remove --source KEY` is the
     documented way back.
7. **Residual limits (documented, not fixed):**
   - A person with shell access and the database URL can still import
     synthetic data on purpose. The flag prevents accidents, not misuse by an
     operator.
   - Ignoring `--allow-synthetic-in-database` for real sources or test
     databases is intentional and harmless.

**Status:** reviewed and hardened. The flag **stays PROVISIONAL**, per the
instruction for this session: the owner decides whether demo imports into
`lexflow` remain allowed at all.

**Tests (`tests/test_judgment_import.py`):**
- the three live-like tests now pretend the connection is to `lexflow` via
  `pretend_connected`;
- new: 11 test-name cases; a test that the connected name is read from the
  server; a test that a URL naming `lexflow_test` while connected to `lexflow`
  is refused with every flag combination, and an empty name is refused;
- refusal outside test databases for `lexflow`, `lexflow_latest`, `contest`
  and `lexflowtest`.

**Results:**
- `pytest tests/test_judgment_import.py`: **48 passed**, exit 0;
- `ruff check`: exit 0;
- `mypy`: exit 0.

**Documentation:** `server/README.md` now describes the connected-name rule,
the whole-part rule and the provisional demo flag.

#### M9.6 addendum — one rule for test-database names (2026-10-24)

- The settings guard that allows `LEXFLOW_AI_PROVIDER=scripted` only with a
  test or e2e database (`lexflow/config.py: _is_test_database`) had the same
  two gaps as the import command: the substring rule, and the URL name
  without its `dbname`/`service` query.
- There is now one rule, `config.is_test_database_name`, which needs a whole
  name part "test" or "e2e". The import command uses it (its own copy was
  removed). The settings guard also refuses URLs with `dbname`/`service`
  parameters.
- `tests/test_analysis_config.py` adds 4 refusal cases: `lexflow_latest`,
  `contest`, `lexflow_test?dbname=lexflow` and `lexflow_e2e?service=live`.
- In preparation for B7, `runs.analyse` was split, with no change in
  behaviour:
  - the provider call, parsing and validation moved into `check_answer`,
    which needs no database;
  - the retry decision moved into `retry_due`.
  `analyse` and `complete` call them.
- **Results:**
  - `pytest tests/test_judgment_import.py tests/test_analysis_config.py tests/test_analysis_provider.py`:
    **129 passed**, exit 0, before the 4 new config cases;
  - `tests/test_analysis_config.py`: **10 passed**, exit 0;
  - `tests/test_analysis_runs.py`: **40 passed**, exit 0, after the split;
  - ruff and mypy: exit 0.

### M9.7 — Offline evaluation harness (2026-10-24)

- **What it is:** `server/scripts/evaluate_analysis.py` with the fixture
  `server/tests/fixtures/analysis/synthetic-gold-v1.json`.
  - The fixture is SYNTHETIC: an invented case, 3 passages and 1 judgment,
    with 68 scenarios. It has no `source`, so the judgment importer refuses
    it, and it is kept apart from the judgment collection and its fixtures.
  - It runs the real code with no network and no database:
    1. answer scenarios: a scripted provider feeds `runs.check_answer` (the
       worker's provider call, parsing and validation, split out of
       `analyse` in M9.6);
    2. provider scenarios: the real `GeminiProvider` with a scripted SDK
       client, and building a real client is refused;
    3. retry scenarios: attempts are replayed through `check_answer` and the
       worker's `retry_due`;
    4. configuration scenarios: `provider_for` on explicit settings
       (`_env_file=None`; `.env` is not read).
  - **There is no pass mark.** Each scenario states its expected outcome.
    Mismatches and user-facing messages containing operator words are
    listed, and either makes the exit status 1.
- **Coverage, scenarios per category:**

  | Category | Scenarios | What it covers |
  |---|---:|---|
  | quote-fidelity | 5 | exact, normalised, altered, too-short, wrong passage |
  | fabricated-citation | 5 | law-report, neutral, case name, known judgment (kept), unknown judgment |
  | evidence-reference | 5 | missing, foreign, stale (the earlier text of a passage), judgment-as-fact, injected id |
  | contradiction | 5 | planted conflict (kept), one source, same quote, nested quote, non-contradiction |
  | outcome | 3 | outcome key, outcome wording, paraphrase |
  | malformed-output | 11 | not JSON, cut JSON, truncated then OK, truncated twice, array, wrong type, bad flag, fenced, extra keys, empty object, provider bug |
  | insufficient-evidence | 3 | no passages (nothing sent), the model's flag, an issue without facts |
  | provider-failure | 16 | 429 plain/minute/daily, 400/401/403/404/500/503, timeout, unreachable, blocked prompt/finish, no candidates, blank, MAX_TOKENS |
  | retry | 6 | rate limit exhausted, daily quota, timeout then OK, auth, 503 then quota, unreadable twice |
  | configuration | 9 | disabled, unknown, wrong-case name, no key, no model, Gemini OK, scripted with a test database, scripted with a live database, scripted with `?dbname=` |

- **Result** (`python scripts/evaluate_analysis.py --write`, exit 0):
  - **68 scenarios, 68 as expected, 0 not as expected**;
  - 73 user-facing messages checked, 0 with operator words;
  - written to `docs/verification/phase5/analysis-eval.json` and
    `analysis-eval.md`, with fixture SHA-256
    `c3c73b901008480c04d27443d14a8f4a8c59778da5b5dcf5fe92ceeef9a8a071`.
- **Limitations, shown and kept by design:**
  1. `ct-non-contradiction`: two verified quotes that do not conflict are
     kept, because validation proves provenance, not conflict.
  2. `oc-paraphrase`: a paraphrased prediction passes the wording patterns.
  This harness measures LexFlow's checks and error handling. It says nothing
  about the quality of any model's legal analysis.
- **Tests:** `tests/test_analysis_evaluation.py` (3 tests, **3 passed**, exit 0):
  1. every scenario behaves as stated and no message is unsafe;
  2. the harness reports three deliberately changed expectations (proof that
     it can fail);
  3. the fixture is synthetic and separate from the collection.
- `ruff check` and `mypy` (136 files): exit 0.

### M9.8 — Full verification (2026-10-24/25)

Every result below is from this session, run after the last code change.
The databases used: `lexflow_test` (recreated by the pytest suite and the
mutation runs; its URL was inspected without printing values and has no
query parameters) and `lexflow_e2e` (recreated by `e2e.py prepare`). Both are
disposable by the project's own design. **`lexflow` was not used by any
check.**

| Check | Command | Result | Exit |
|---|---|---|---|
| Backend tests | `server: python -m pytest -q -p no:cacheprovider` | **906 passed**, 0 skipped, 140.6 s (`pytest-full-m9.log`) | 0 |
| Lint | `server: ruff check .` | all checks passed | 0 |
| Format | `server: ruff format --check .` | 150 files already formatted | 0 |
| Types | `server: mypy` (strict) | no issues, 136 files | 0 |
| Types (Linux) | `server: mypy --platform linux .` | no issues, 147 files | 0 |
| OpenAPI | `server: python scripts/export_openapi.py --check` | up to date | 0 |
| Migrations vs models | `alembic check` on `lexflow_test` only (URL asserted) | no new upgrade operations | 0 |
| Offline evaluation | `server: python scripts/evaluate_analysis.py --write` | 68 scenarios, 68 as expected; 0 unsafe messages | 0 |
| Front end | `npm run check` (eslint, prettier, tsc, api:check, sample-data:check, vitest, build) | 17 files / **178 tests passed**; build OK (`npm-check-m9.log`) | 0 |
| End to end | `npx playwright test` (ports 5174/8001, scripted provider) | **41 passed** (`playwright-m9.log`) | 0 |
| Mutation | `python docs/verification/phase5/run_mutation_checks.py --working-tree` | **61 of 61 caught**, every file restored byte-for-byte, targets unchanged (`mutation-report-working-tree.md`, `mutation-output-working-tree.log`) | 0 |

- **Mutation runner:**
  - It gained `--working-tree` for uncommitted work. In this mode it lists
    each target's SHA-256 instead of a commit, checks the snapshot at the
    end, and writes `-working-tree` report files, so the M7 reports are kept.
  - Anchor P-1 followed the provider change, and C-3's label now says that
    administrators see the setting name.
  - 21 new M9 mutations: M9-1 to M9-21.
- **Logs:**
  - The new logs were scanned for home paths, keys, passwords and database
    URLs. The only key-like string is the fake test key
    `AIzaFAKE-…-not-real`, printed by a failing assertion under mutation
    M9-4.
  - The M7 logs (`pytest-full.log`, `npm-check.log`, `playwright.log`,
    `mutation-*.log/md`) are unchanged.
- **Not run:** none of the planned checks was skipped. No real Gemini call
  was made in any check: tests use fakes, the e2e suite forces the scripted
  provider, and the evaluation refuses to build a real client.

### M9.9 — Records reconciled; session end (2026-10-25)

- **Documents updated:**
  - `docs/PHASE5_PLAN.md`: status line, M8 marked done, new M9 row, §11
    commands, §12 resume steps, new §13 with the M9 decisions;
  - `docs/adr/0019-ai-case-analysis.md`: appended M9 amendment;
  - `docs/SRS.md`: removed the stale "live collection is empty" (it holds
    three labelled SYNTHETIC demo judgments);
  - `docs/TRACEABILITY.md`: FR-18 and NFR-6 rows;
  - `server/README.md`: the synthetic-import rule.
- `docs/IMPLEMENTATION_PROGRESS.md` and `CLAUDE.md` do not exist, are not an
  established convention here, and were not created.
- **Brief:** `docs/DEVELOPMENT_BRIEF.md` SHA-256
  `274ecaed93400f51dd47c42337fbd6e101aa6be366b80d977d1522359b34c2ec`.
  It matches and is unmodified.
- **Git:** branch `master`, HEAD `6b8f865`, no remote. Nothing was committed
  or pushed.
  - Working tree: 31 tracked files modified (+2769/−177). This includes the
    11 files that were already uncommitted at the start, saved in the
    session backup.
  - 10 new untracked paths: `server/scripts/evaluate_analysis.py`,
    `server/tests/test_analysis_evaluation.py`,
    `server/tests/fixtures/analysis/`, and the new verification outputs in
    `docs/verification/phase5/`.
- **Boundaries kept:**
  - no migration applied and no schema change;
  - no application record in `lexflow` read for changes, modified, imported
    or deleted;
  - no paid or real LLM call;
  - no secret printed;
  - no commit, push, remote or branch change;
  - the brief is unchanged;
  - no Phase 6/7, UI redesign, data acquisition or local-LLM work.
- **Phase 5 status: NOT declared complete.** M9 is implemented and verified
  but uncommitted, and the provisional demo-import flag awaits the owner's
  decision.
- **Next step (owner):** review the M9 diff, decide whether
  `--allow-synthetic-in-database` stays, and commit as
  `Phase 5 M9: stabilisation`.

Checkpoint: docs/verification/phase5/checkpoint.json — M9 B0–B9 done (uncommitted); next_action = owner review, flag decision and commit of M9; 2026-10-25.

### M9.10 — Pre-commit review fixes M1, M2, M3, L1 (2026-10-25)

A read-only pre-commit review (2026-10-25) found no critical or high issues,
three medium issues (M1–M3) and some low ones. The owner approved fixing M1,
M2, M3 and L1. Nothing was staged or committed.

- **M1 — correction to M9.6.** Finding 5 in M9.6 said
  `scripts/evaluate_judgment_search.py` "imports only into the fixed
  throwaway `lexflow_eval_test`". That was **wrong**.
  - *Previous assumption:* the scripts swap the database name in
    `TEST_DATABASE_URL` for the constant `lexflow_eval_test`, so they can
    only touch that database.
  - *Gap:* `make_url(raw).set(database=...)` keeps the URL's query. With
    `?dbname=lexflow`, psycopg connects to `lexflow`. This was shown
    offline, without connecting.
    - The judgment-search evaluation would then migrate that database and
      import its synthetic judgments into it, with no flag.
    - `scripts/evaluate_retrieval.py` would load its fictional documents
      there.
    - The final drop is by explicit name (`lexflow_eval_test`), so the
      cleanup itself never dropped another database.
  - The gap was latent: the configured URL has no query parameters, and the
    test suite now refuses such a URL.
  - *Fix:* both `eval_url()` functions refuse a `dbname` or `service` query
    parameter before returning a URL, the same rule as `tests/conftest.py`,
    `scripts/e2e.py` and the settings guard. Both `main()` functions now call
    `eval_url()` first, before reading a file, loading a model or connecting.
  - *Tests:* new `tests/test_evaluation_scripts.py`, 18 tests across both
    scripts. They cover:
    - 4 refused URLs: `?dbname=lexflow`, `?service=live`, `dbname` mixed with
      `sslmode`, and `dbname` equal to the throwaway name;
    - 4 accepted forms: plain, without a password, `?sslmode=disable` and
      `?connect_timeout=5`;
    - `main()` refusing before any side effect. `create_engine`, `recreate`,
      `migrate`, the model loader and `load_set` are replaced with functions
      that fail the test if called.
    No script was run against a database. With the guard stripped (in
    memory only), the bad URL passes, so the tests would catch its removal.
- **M2 — the outcome-wording filter, narrowed (validator `grounding-3`).**
  - Under `grounding-2`, any "likely/unlikely/probably" within 40 characters
    of "win/lose/succeed/prevail" was removed. That dropped grounded facts
    such as "The plaintiff is likely to lose goodwill if the mark continues
    in use".
  - Now a predictive word must meet a litigation outcome:
    1. an outcome verb with the case, a claim, an appeal or similar ("is
       likely to win the suit");
    2. a bare outcome verb ("is likely to succeed.", "will certainly lose on
       the notice");
    3. a litigation subject that will fail or be dismissed, allowed, granted
       and so on;
    4. a court that will grant, award, dismiss and so on a relief or a case;
    5. a court that will rule in someone's favour or side with a party;
    6. chances, prospects or odds of success or winning;
    7. "N% chance of" with an outcome word nearby. "A 70% probability that
       the signature is forged" is not matched.
  - Filtering is not disabled; predictions are still removed and counted as
    `outcome-wording`.
  - `VALIDATOR_VERSION` is now `grounding-3`, because the rules changed.
    Runs that recorded `grounding-2` are not reinterpreted.
  - *Tests* (`test_analysis_validation.py`): 14 predictions removed and 12
    factual statements kept. The factual ones include the review's three
    examples, "likelihood of confusion", "a 70% probability that the
    signature is forged" and "the court will allow the parties two weeks".
    The existing combined outcome test is unchanged, with 6 removals.
  - *Evaluation fixture:*
    - `oc-paraphrase` now uses "The plaintiff's position on prior use looks
      the stronger one", because "the court will side with" is now caught.
    - New scenarios: `oc-court-remedy` (removed), `oc-fact-goodwill` (kept)
      and `oc-fact-tender` (kept).
    - The fixture's SHA-256 is now
      `cdfd191042b72a13761c3cf1bd2440b4f4ebc018b50598d47922144840e7e815`.
  - *Limitation (documented in `validation.py`, plan §13 and ADR 0019):*
    these are patterns. They miss paraphrased predictions and can still
    remove an unusual factual sentence that reads like one, so they cannot
    reliably tell every legal prediction from every fact. Validation proves
    provenance, never legal correctness.
- **M3.** `docs/verification/phase5/README.md` now:
  - lists the M9 outputs separately from the M7 ones, which are kept and
    marked historical;
  - replaces "No Gemini call was made during Phase 5" with the recorded
    facts. No automated check calls Google. The owner's real runs are in
    M8e (four runs, seven requests, run `4fc9ab87` ready) and M9.0 (three
    more runs);
  - replaces "0011 not applied" with the recorded M8d state (applied
    2026-10-20, `alembic current` 0011).
  The database was not queried; these are records, and the README says so.
- **L1.** `checkpoint.json` `updated` is now 2026-10-25.
- **Results (all 2026-10-25, offline unless noted):**

  | Command (from `server/` unless noted) | Result | Exit |
  |---|---|---|
  | `pytest -q tests/test_evaluation_scripts.py` | 18 passed | 0 |
  | `pytest -q tests/test_analysis_validation.py tests/test_analysis_output.py tests/test_analysis_evaluation.py tests/test_evaluation_scripts.py` | 95 passed | 0 |
  | `pytest -q tests/test_analysis_runs.py tests/test_analysis_provider.py tests/test_analysis_config.py tests/test_analysis_evidence.py tests/test_judgment_import.py` (disposable `lexflow_test`) | 183 passed | 0 |
  | `pytest -q -p no:cacheprovider` (full suite; `docs/verification/phase5/pytest-full-m9-review-fixes.log`) | **950 passed** (906 + 18 + 26 new) | 0 |
  | `python scripts/evaluate_analysis.py --write` | 71 scenarios, 71 as expected; 75 messages, 0 with operator words; validator `grounding-3` (report rewritten) | 0 |
  | root: `python docs/verification/phase5/run_mutation_checks.py --dry-run` | 61 of 61 snippets found exactly once (the full mutation run was not repeated) | 0 |
  | `ruff check .` / `ruff format --check .` | pass / 151 files formatted | 0 / 0 |
  | `mypy` / `mypy --platform linux .` | 137 / 148 files, no issues | 0 / 0 |
  | `python scripts/export_openapi.py --check` | up to date (no API change) | 0 |

  - The front end and Playwright were not rerun because no front-end, API or
    e2e file changed. `npm-check-m9.log` and `playwright-m9.log` remain the
    latest results.
  - The full mutation run was not repeated either. Its M9-15 guard (outcome
    wording) still points at the unchanged `outcome_wording` line.
- **Boundaries:** no migration and no schema change; no `lexflow` record
  read for changes or modified; no LLM call; no secret printed; nothing
  staged or committed; the brief is unchanged.
- **Next step (owner):** stage the M9 working tree for review and commit it
  as `Phase 5 M9: stabilisation`.

Checkpoint: docs/verification/phase5/checkpoint.json — M9 B0–B9 and review fixes done (uncommitted); next_action = owner stages and commits M9; 2026-10-25.

### M9.11 — Checkpoint reconciliation, records only (2026-10-25)

The owner approved this records-only cleanup after the final pre-commit
review. Only `docs/verification/phase5/checkpoint.json` and this log changed.
Earlier entries and checkpoint values were not rewritten.

- `m8.pending` (written 2026-10-20) is kept verbatim. The new
  `m8.pending_current_status_2026_10_25` gives each item's current status:
  - `reverification` is superseded:
    - the full backend suite passed with 906 tests (M9.8) and then 950 tests
      (M9.10);
    - the full mutation run caught 61 of 61 **before** the M2 filter change,
      and after it only an anchor dry run was done.
  - `precedent_comparison_live` is superseded: precedent comparison ran live
    against three SYNTHETIC demo judgments, as recorded in the 2026-10-20
    observation (M9.0; the database was not queried).
  - `contradiction_detection_live` and `commit` remain open.
- The new top-level `current_status_2026_10_25` clarifies the pre-M9
  top-level keys `gemini_calls_made`, `backend_tests`, `frontend_tests`,
  `mutation_checks` and `uncommitted`. It also lists the known limitations
  and points to the open low findings L2 and L3.
- `status` and `next_action` now record that, besides staging and
  committing M9, two decisions remain open for the owner:
  1. whether to investigate the planted 2015/2017 contradiction that live
     analysis did not report;
  2. whether to approve a real judgment source for future dataset work.
  This replaces "No implementation is pending" in M9.10. The M9 batches are
  complete; follow-up remains.
- Unchanged: the provisional `--allow-synthetic-in-database NAME` decision
  and every other checkpoint value. The checkpoint JSON was validated and
  replaced atomically.

Checkpoint: docs/verification/phase5/checkpoint.json — M9 done (uncommitted); next_action = owner stages and commits M9, then decides on the 2015/2017 contradiction investigation and a real judgment source; 2026-10-25.
