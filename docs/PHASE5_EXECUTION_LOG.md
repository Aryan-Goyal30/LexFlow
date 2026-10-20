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
| M1 | Contract, settings, migration 0011 (scratch only), output schema | see below |
| M2 | Evidence assembly + prompt v1 | pending |
| M3 | Provider layer | pending |
| M4 | Validation | pending |
| M5 | Runs: API, worker, audit, authorisation | pending |
| M6 | User interface | pending |
| M7 | Verification and documents | pending |
| M8 | Live migration 0011 + manual smoke | **owner-gated: not done in this run** (applying 0011 to live was explicitly not authorised) |

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

Checkpoint: M1 committed; next M2 (evidence assembly and prompt v1).
