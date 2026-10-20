# Phase 5 execution log — AI case analysis with Google Gemini

Started 2026-10-20. Scope: `docs/DEVELOPMENT_BRIEF.md` §4 Phase 5 and
`docs/PHASE5_PLAN.md` (decisions D1–D5 approved, plan §9). No Phase 6–7 work.

## How to resume (read this first)

1. `git log --oneline` — milestone commits start with `Phase 5 M<n>`.
2. Read `docs/verification/phase5/checkpoint.json` (machine-readable) and the
   **Checkpoint** line at the end of this file.
3. Check `alembic current` (in `server/`) against the checkpoint. The live
   `lexflow` database stays at **0010** until the owner approves M8.
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
| M8 | Live migration 0011 + manual smoke | **prepared and rehearsed; not applied** (owner-gated: applying 0011 to live was explicitly not authorised) |

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

## M8 — Live migration 0011 (prepared and rehearsed; NOT applied)

Applying 0011 to the live database was explicitly not authorised in this
run, so M8 stops at the rehearsal:

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

What the owner does to finish M8 (when they decide to):

1. Stop the API and worker; take a fresh dump of `lexflow` and record its
   SHA-256 (the rehearsal dump above will be out of date).
2. From `server/`: `.venv\Scripts\alembic upgrade head`, then
   `.venv\Scripts\alembic check`. Recovery: `alembic downgrade 0010`
   (rehearsed; drops only `analysis_runs`) or restore the dump.
3. Restart the API and worker on the new code. With
   `LEXFLOW_AI_PROVIDER=disabled` (the default) nothing else changes.
4. Only for the optional manual smoke: put `GEMINI_API_KEY` and a
   `GEMINI_MODEL` chosen from Google's current model list into
   `server/.env` privately, set `LEXFLOW_AI_PROVIDER=gemini`, restart, and
   analyse **one sample case containing only synthetic documents** (D1).
   Check Google's current terms, structured-output support and pricing for
   the chosen model first.

Until then the running API and worker (still the Phase 4 processes) are
unaffected; restarted on the Phase 5 code without 0011 they report analysis
as unavailable ("migration 0011 is not applied") and keep working.

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
| Live database at 0011 | **Not done** — owner-gated (M8) |
| A real Gemini run | **Not done** — no key configured; no Gemini call was made |

## Limitations

- No Gemini call was made: real model behaviour (adherence to the schema,
  quote accuracy, latency, cost) is unmeasured. The model name,
  structured-output support and prices were not verified against Google's
  documentation in this run; the owner chooses and checks them.
- Validation proves provenance (the quote is in the cited passage, the
  judgment was retrieved), not legal correctness.
- The live judgment collection is empty, so live results will say that no
  precedents were available.
- Only sample cases may be analysed (D1) until a privacy, confidentiality
  and provider-terms review allows client material.
- The live database is at 0010; analysis cannot run there before M8.

Checkpoint: Phase 5 M1–M7 done and committed; M8 prepared and rehearsed,
**awaiting the owner** (live migration and optional manual smoke).
