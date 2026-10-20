# Phase 5 plan — AI case analysis with Google Gemini

Status (2026-10-20): **decisions approved (§9); implementation recorded in
`docs/PHASE5_EXECUTION_LOG.md`.** Planned at `e122d11` (Phase 4 complete).
Scope from `docs/DEVELOPMENT_BRIEF.md` §4 Phase 5. Machine-readable state:
`docs/verification/phase5/checkpoint.json`.

## 1. Brief: scope and "done when"

- `AiService` on the front end becomes a client of a backend endpoint (e.g.
  `POST /cases/{id}/analysis`).
- Backend: retrieve the case's chunks and candidate precedents, ask the LLM for
  **structured JSON** matching `types/ai.ts` (facts with source document and
  page, issues, precedent comparisons, contradictions, judgment summaries).
- **Validate before showing:** reject output citing a document or judgment
  that was not retrieved; drop facts without a source; say so when evidence
  is insufficient.
- Store each run (model, prompt version, inputs, timestamp).
- UI: every fact links to its document and page.
- **Done when:** every displayed claim has a working source link; a test proves
  an output citing an unknown judgment is rejected; the decision-support note
  is shown with every result.

## 2. Repository findings (verified)

| Area | What exists | Path |
|---|---|---|
| AI contract | `ExtractedFact{id,statement,sourceDocumentId?}`, `LegalIssue{relatedFactIds}`, `Precedent{citation,court,year,summary,relevance,similarities,differences}` (no judgment id, page or passage), `Contradiction{sourceDocumentIds}`, `CaseAnalysis{caseId,generatedAt,…,outcomeAssessment?}`. Hand-written, not generated from OpenAPI. | `src/types/ai.ts` |
| AI seam | `AiService{connected, analyzeCase}`; only implementation "not connected" (precedent search removed in Phase 4). | `src/services/ai/aiService.ts` |
| Hook | `useAiAssistant`: guards (no call when disconnected, discard stale/late responses, reject `caseId` mismatch, one run at a time). | `src/hooks/useAiAssistant.ts` (+ `.test.tsx`) |
| UI | `AnalysisTab` (inputs panel from real case data, disabled "Analyse case", results view; `outcomeAssessment` deliberately not displayed), `DecisionSupportNote`, `PrecedentCard` (renders `relevance` as %). | `src/components/workspace/AnalysisTab.tsx`, `AiNotices.tsx`, `PrecedentCard.tsx` |
| Evidence: case | Page-aware `DocumentSection`/`DocumentChunk` (exact offsets, SHA-256), job status `ready`; case retrieval `keyword/semantic/hybrid` (live docs only). Link helper `documentTextPath(caseId, docId, section)`. | `server/lexflow/services/retrieval.py`, `models.py`, `src/lib/paths.ts` |
| Evidence: judgments | `judgments.search(session, mode, q, Filters, provider)` → best passage per judgment; `JudgmentChunk` offsets; `judgmentPath(id, section)`. **Live collection is empty** (no approved source). | `server/lexflow/services/judgments.py` |
| Access | `authz.load_case(..., Action.VIEW)`; staff router; Client accounts never reach staff routes. No analysis action yet. | `server/lexflow/authz.py`, `main.py` |
| Audit | `AuditLog.record(action, actor, target, case_id, details)`; details reject keys containing password/token/cookie/secret/hash/session; values ≤ 200 chars. | `server/lexflow/audit.py` |
| Background work | DB-backed worker (claim with lease, `SKIP LOCKED`, retries, hand-back); pattern reusable for analysis jobs. | `server/lexflow/worker.py`, `services/extraction_queue.py` |
| Settings | pydantic-settings from `server/.env` (git-ignored); no secret settings yet. | `server/lexflow/config.py`, `.env.example` |
| HTTP clients | `httpx`, `requests`, `google.genai` not installed; `httpx2` present only as a transitive dependency. | `server/requirements*.txt` |
| Migrations | head **0010** (live `lexflow` at 0010). | `server/migrations/versions/` |
| Conventions | milestone commits `Phase N M<n>`, execution log + `docs/verification/phaseN/` (README, checkpoint.json, logs, mutation runner), ADRs, synthetic fixtures for tests, fakes only in test code, OpenAPI → generated TS types. | `docs/` |

## 3. Proposed architecture

```
AnalysisTab ─ useAiAssistant ─ aiService (HTTP client)            [React: no key, no prompt]
      │ POST /api/cases/{id}/analysis-runs   GET …/analysis-runs/{runId}
FastAPI (staff router, authz) ── creates AnalysisRun "queued" ── audit
      │
Worker (existing loop, new job kind) ─ claim run (lease)
  1. assemble evidence (selected documents' ready chunks, case fields, timeline,
     judgment passages) within limits; give each an opaque id (D1…, J1…)
  2. render prompt vN (versioned file) + JSON schema
  3. provider.generate(prompt, schema)  ← GeminiProvider (backend only)
  4. validate (schema → citations → quotes → drop/reject) → store result
```

- **Provider interface** `lexflow/analysis/provider.py`:
  `generate(prompt, schema, *, timeout) -> RawOutput`. Implementations:
  `GeminiProvider` (real), `ScriptedProvider` (tests and e2e only; refused
  unless `LEXFLOW_ENV=test` or the database name contains "e2e", like the
  synthetic-judgment gate).
- **Settings** (all backend, `server/.env`): `LEXFLOW_AI_PROVIDER`
  (`disabled` default | `gemini`), `GEMINI_API_KEY` (pydantic `SecretStr`,
  never logged, never in responses or OpenAPI), `GEMINI_MODEL` (required when
  enabled; no hard-coded default — choose from Google's current model list at
  implementation time), `LEXFLOW_AI_TIMEOUT_SECONDS` (90),
  `LEXFLOW_AI_MAX_INPUT_CHARS` (60,000), `LEXFLOW_AI_MAX_DOCUMENTS` (20),
  `LEXFLOW_AI_MAX_PRECEDENTS` (8), `LEXFLOW_AI_RUNS_PER_USER_PER_HOUR` (10),
  `LEXFLOW_AI_ALLOW_CLIENT_DATA` (`false` default: only sample/synthetic cases
  may be analysed until the owner confirms the data terms below).
- **Dependency decision (open, D3):** (a) official `google-genai` 2.31.0
  (dry run: +15 packages incl. `cryptography`, `google-auth`, `httpx`,
  `websockets`, `tenacity`, `requests`) — maintained, typed, structured-output
  support; or (b) the REST `generateContent` endpoint through the standard
  library (as `lexflow.cli.models download` does) — no new dependencies, more
  code to own. **Recommendation: (a)**, pinned with pip-compile, behind the
  provider interface so it can be swapped.
- **Evidence ids, not free-form citations.** The prompt lists each evidence
  item with an opaque id (`D3` = chunk 3 of document X, page 2; `J1` = judgment
  Y's passage). The model may cite only these ids. The server maps ids back to
  `(document_id, section, page, chunk_id)` / `(judgment_id, section, chunk_id)`.
- **Structured output.** JSON schema derived from the pydantic output model;
  sent as the response schema; the response is parsed with pydantic regardless
  (the model's adherence is never trusted).
- **Validation pipeline (server, before storing as "ready"):**
  1. JSON parses and matches the schema; else one retry, then run `failed`
     (`invalid-output`).
  2. Every cited id exists in this run's evidence set; a fact without a valid
     source is **dropped**; a precedent comparison for a judgment that was not
     retrieved **rejects** that item (brief: "an output citing an unknown
     judgment is rejected").
  3. Each fact/contradiction carries a short supporting quote that must occur
     verbatim (whitespace-normalised) in the cited chunk; otherwise dropped.
  4. Issues may reference only surviving facts; dangling references removed.
  5. `outcomeAssessment` is never requested and is discarded if returned
     (Phase 7).
  6. Counts of dropped/rejected items and reasons stored and shown ("3 items
     removed: no valid source").
  7. If nothing survives, or the evidence set was empty, the run is `ready`
     with `insufficientEvidence: true` and an explanation — never a guess.
- **Contract change (`types/ai.ts`)**: add `runId`, `model`, `promptVersion`,
  `insufficientEvidence`, `removed: {count, reasons}`; facts gain
  `source: {documentId, section, page, chunkId, quote}`; precedents gain
  `judgmentId`, `passage: {section, page, chunkId}`, drop `relevance` (no
  model-made scores; the retrieval rank is shown instead); contradictions gain
  per-source references; add `judgmentSummaries`. Make `types/ai.ts` alias the
  generated OpenAPI types (one contract, drift-checked), as `types/index.ts`
  does.
- **UI**: "Analyse case" with an explicit selection of documents (default: all
  with ready text), a notice that the selected material is sent to Google's
  Gemini API, progress (polling the run), results with links to
  `documentTextPath(…, section)` and `judgmentPath(…, section)`, removed-item
  count, run history (model, prompt version, time), `DecisionSupportNote`
  with every result. Not legal advice; no outcome prediction.

## 4. Data model — migration needed: yes (0011, additive)

`analysis_runs`: `id`, `case_id` → cases (cascade), `requested_by_id` → users
(set null), `status` (`queued|running|ready|failed`), `reason_code`,
`reason`, `attempts`, `lease_expires_at`, `worker_id`, `provider`, `model`,
`prompt_version`, `evidence` (JSONB: ids → document/chunk/judgment refs with
content SHA-256, selection and limits used), `result` (JSONB: validated output
only), `removed` (JSONB counts/reasons), `usage` (JSONB token counts if
returned), `created_at`, `started_at`, `finished_at`. Indexes on
`(case_id, created_at)` and `(status, created_at)`. Raw model output is **not**
stored by default (it may contain unsupported text); a debug setting may keep
it for synthetic cases only.

Procedure (as Phases 3–4): autogenerate against a scratch database, review,
upgrade/check/downgrade/upgrade on scratch; before the live change a fresh
`pg_dump` + SHA-256, restore into a scratch database, fingerprint comparison,
rehearsal, then `alembic upgrade head` with the owner's go-ahead. Downgrade
drops only `analysis_runs` (runs can be re-made).

## 5. Security and privacy

- Key only in `server/.env` (git-ignored) as `SecretStr`; never sent to
  React, never logged, never audited; a test scans responses/OpenAPI/logs for
  it. `.env.example` documents the variable without a value.
- **Data leaves the machine:** selected case text (and judgment passages) is
  sent to Google. Gemini API terms (page updated 2026-04-28,
  <https://ai.google.dev/gemini-api/terms>): *Unpaid Services* — Google uses
  submitted content and responses "to provide, improve, and develop" its
  products, human reviewers may read them, and "Do not submit sensitive,
  confidential, or personal information to the Unpaid Services"; *Paid
  Services* — prompts and responses are not used to improve products, but are
  logged "for a limited period of time" for abuse detection and legal
  disclosures, and may be cached in any country where Google has facilities.
  **Gate (D1):** real client material only on a paid (billed) project, after
  the owner reads the current terms (and any client-confidentiality duties);
  until then `LEXFLOW_AI_ALLOW_CLIENT_DATA=false` restricts analysis to sample
  and synthetic cases.
- Prompt injection: document text is delimited data; instructions inside it
  cannot add evidence because every claim is re-checked against the evidence
  set; the model has no tools.
- Authorization (D4): start a run — Administrator and advocates on the case
  (new `Action.RUN_ANALYSIS`); read runs — staff who may view the case;
  Clients never. Audited: `analysis.requested`, `analysis.completed` /
  `failed` (counts, model, prompt version — never text).
- Rate and cost limits: per-user hourly cap, one active run per case, input
  character cap, timeout; 429/5xx retried at most twice with backoff, then
  `failed` (`provider-rate-limited` / `provider-unavailable`); safety blocks →
  `failed` (`provider-blocked`).

## 6. Milestones (each: tests, log entry, local commit `Phase 5 M<n>`)

| # | Milestone | Acceptance criteria | Size |
|---|---|---|---|
| M0 | **Owner decisions** D1–D5 (below) | Recorded in this file | owner |
| M1 | Contract + migration 0011 (scratch only) + settings | Output pydantic model and JSON schema; `analysis_runs`; `alembic check` clean; settings validated (key required when enabled, never echoed) | M |
| M2 | Evidence assembly + prompt v1 | Deterministic evidence set within limits from selected ready documents (live only), timeline, case fields, ≤ N judgment passages (none when the collection is empty); opaque ids; prompt file versioned; tests | M |
| M3 | Provider layer | `GeminiProvider` (timeouts, retries, error mapping, no key leakage), `ScriptedProvider` gated to tests/e2e; tests with mocked transport only | M |
| M4 | Validation | Unknown document/judgment ids rejected; wrong page/chunk rejected; quote not in chunk → dropped; facts without source dropped; dangling issue refs removed; outcomeAssessment discarded; insufficient evidence path; malformed JSON → retry → failed | L |
| M5 | Runs: API + worker + audit + authz | `POST/GET /api/cases/{id}/analysis-runs[/{runId}]`; worker job kind; one active run per case; rate limit; Client 403, outsider 404; audit events; OpenAPI + TS types | L |
| M6 | UI | `aiService` HTTP implementation; document selection; data-transmission notice; progress; results with working source links; removed-items count; run history; disclaimer on every result; Vitest | M |
| M7 | Verification + docs | pytest, `npm run check`, Playwright with the scripted provider (no network), mutation checks on validation/authz/key handling, ADR 0019, SRS/architecture/traceability (adds the *analyse case* sequence), execution log | M |
| M8 | Live migration 0011 + optional manual smoke | Gated procedure (§4); then **one** manual run on a **synthetic** case with a real key, only after D1–D2 | owner-gated |

Total estimate: comparable to Phase 4 (seven to eight milestones).

## 7. Tests (planned)

- **Unit:** schema validation; evidence-id mapping; quote check (exact,
  whitespace, Unicode); every rejection rule; limits; prompt rendering
  deterministic; key redaction.
- **Tampering:** model cites `D99` (unknown), `J5` (judgment not retrieved),
  right document wrong page, invented citation string, fact with no source,
  quote not in chunk, issue pointing at a dropped fact, extra fields, an
  `outcomeAssessment` → each removed or the run rejected as specified.
- **Provider failures (mocked):** timeout, 429, 500, safety block, empty
  candidate, non-JSON, truncated JSON, schema-valid but empty → specified
  status and reason; no partial result stored.
- **Authorization:** each role start/read; Client 403; outsider 404; deleted
  documents never in evidence; archived case (read allowed, start refused?
  D4).
- **Empty evidence:** no ready documents; empty judgment collection.
- **Frontend (Vitest + MSW):** run lifecycle, stale/late responses, links,
  removed counts, notice, disclaimer, errors.
- **Playwright:** full flow on the e2e database with the scripted provider;
  source links open the right document page and judgment page.
- **Never** a real Gemini call in automated tests; network blocked for the
  provider in tests.

## 8. API usage (estimate, to confirm at implementation)

Automated tests: 0 calls. Manual smoke (M8): a few calls on a synthetic case.
Per real run: input up to ~60,000 characters (roughly 15,000 tokens, plus
prompt and schema) and an output cap of a few thousand tokens; one retry at
most on malformed output. Cost depends on the model and tier chosen (D2) —
check Google's current pricing; no figure is assumed here.

## 9. Owner decisions (approved 2026-10-20)

Approved by the owner at the start of the implementation run and applied as
follows.

- **D1 Data privacy — approved.** Initially analyse only synthetic or sample
  cases. Never send real confidential client material to Gemini during this
  implementation. Gemini receives the selected case content; production use
  requires a separate privacy, confidentiality and provider-terms review. A
  paid subscription alone does not establish legal or contractual compliance.
  *Applied:* `LEXFLOW_AI_ALLOW_CLIENT_DATA=false` (default) refuses any case
  not marked as sample; the UI states what is sent to Google before every
  run and asks for confirmation.
- **D2 Model — approved.** Gemini API through a configurable model setting
  (`GEMINI_MODEL`, no hard-coded default). Key read only from backend
  configuration `GEMINI_API_KEY`, configured manually by the owner in
  `server/.env` (never requested, printed or exposed). Missing key or model →
  analysis reported unavailable with a clear reason, never a crash. Model
  names, structured-output support and pricing must be checked against
  Google's official documentation by the owner when choosing the model.
- **D3 Dependency — approved.** Official `google-genai` Python SDK, pinned
  with pip-compile like every other dependency.
- **D4 Roles — approved.** Only the Administrator and advocates authorised on
  the case (lead or associate) may start an analysis; archived cases are
  refused; every read of past results is authorised (`view` on the case;
  inaccessible cases answer "not found"); audit events follow existing
  conventions with no secrets or prompt text.
- **D5 Precedents — approved.** Analysis remains usable with no judgments;
  the result states explicitly that no precedents were available for
  comparison; judgments are never invented.

## 10. Risks

Confidentiality (data to a third party); hallucinated content surviving as
uncheckable prose (mitigated by evidence ids + quote checks + removal); model
or API changes (model name configurable, provider interface); cost runaway
(caps, rate limit, one run per case); prompt injection (validation is
independent of the model); empty judgment collection limits usefulness;
long-running calls (worker, timeouts); contract churn affecting Phase 6
(design `result` JSON so review state can be attached per item later).

## 11. Verification commands (when implemented)

`server`: `.venv\Scripts\python -m pytest -q`, `ruff check .`, `ruff format
--check .`, `mypy .`, `mypy --platform linux .`, `python
scripts/export_openapi.py --check`, `alembic check`. Root: `npm run check`,
`npx playwright test`. Mutation: `docs/verification/phase5/run_mutation_checks.py`
(to be written).

## 12. How to resume

1. Read `docs/verification/phase5/checkpoint.json` and §9 here.
2. If D1–D5 are recorded, start **M1**: autogenerate migration 0011 against a
   scratch database (never `lexflow`), add the output schema and settings.
3. Prompt to continue: *"Implement Phase 5 milestone M1 from
   docs/PHASE5_PLAN.md (decisions D1–D5 as recorded); scratch-only migration;
   mocked provider; no Gemini calls."*
