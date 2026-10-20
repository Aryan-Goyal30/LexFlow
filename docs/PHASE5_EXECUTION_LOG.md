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
| M4 | Validation | done |
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

Checkpoint: M4 committed; next M5 (runs: API, worker, audit, authorisation).
