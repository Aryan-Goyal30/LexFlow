# Phase 6 plan — Lawyer review and case brief export

Status (2026-10-25): **complete.**
- Closure commit "Phase 6: lawyer review and case brief export", whose
  parent is `5302e41` (Phase 5 closure).
- All acceptance criteria AC1–AC10 are met, with fresh evidence in
  `docs/verification/phase6/`.
- Migration 0012 was applied to the live `lexflow` on 2026-10-25, after a
  verified backup (log B8a).
- The record is in `docs/PHASE6_EXECUTION_LOG.md` and
  `docs/verification/phase6/checkpoint.json`.

## 1. Brief: scope and "done when" (`docs/DEVELOPMENT_BRIEF.md`, Phase 6)

- For each finding: accept, reject, or edit, with an optional note.
- Record review actions on the matter timeline.
- Export a case brief (PDF or DOCX) containing only accepted findings, with
  citations.
- **Done when:** unreviewed findings are visibly marked as unreviewed, and
  the export contains only accepted findings.

No separate lab or experiment specification exists in the repository; the
brief above is the source of the requirements (searched 2026-10-25).

## 2. What Phase 6 builds on (verified 2026-10-25)

| Area | Existing | Where |
|---|---|---|
| Findings | each ready run's validated result: facts `F1…`, issues `I1…`, precedents `P1…`, contradictions `C1…`. Ids are unique **within a run** | `analysis_runs.result` (JSONB), `AnalysisResultOut` |
| Provenance | evidence record (chunk ids, hashes), `pipeline` versions, `evidence.changed` (sources changed since the run) | `analysis/evidence.py`, `api/analysis.py` |
| Access | `authz.load_case` + `Action`; `RUN_ANALYSIS` = Administrator, lead, associate; `VIEW` = staff on the case; archived cases refuse non-read actions; clients never reach staff routes | `lexflow/authz.py` |
| Audit | `AuditLog.record` (actor, target, case, details; counts and codes only, no text) | `lexflow/audit.py` |
| Timeline | `timeline_events` (date, label, description, actor). Shown to staff on the case, never in the client portal. **The analysis evidence builder sends the 30 most recent rows to the model** (`TIMELINE_MAX`) | `models.py`, `services/cases.py`, `analysis/evidence.py` |
| Documents | `python-docx` 1.2.0 is already a dependency (used for extraction) | `requirements.in` |
| UI | AI Analysis tab: results, source links, history, `evidence.changed` notice | `src/components/workspace/AnalysisTab.tsx`, `src/hooks/useCaseAnalysis.ts` |

## 3. Design (decisions D6-1 … D6-9; reasons and alternatives in ADR 0020)

- **D6-1 Review persistence (migration 0012, additive).**
  - `analysis_finding_reviews` holds the current state of one finding: run,
    case, finding kind and id, status, reviewed wording, note, version,
    reviewer and time. It is unique on (run, finding id).
  - `analysis_finding_review_events` is an append-only history: one row per
    change, unique on (review, version).
  - The run's `result` is **never changed**: the original AI wording stays
    the record, and reviewed wording is stored beside it.
- **D6-2 States.**
  - The states are `unreviewed` (no row, or cleared), `accepted`, `edited`
    (accepted with lawyer wording; the wording is required) and `rejected`
    (an optional reason).
  - Clearing a decision returns the finding to `unreviewed` and keeps the
    history.
  - Every change sends the version it saw. A stale version answers 409, and
    a request that changes nothing creates no event (so it is idempotent).
- **D6-3 What may be reviewed.**
  - Only findings of a **ready** run of the same case. The kind and id must
    exist in that run's result.
  - The edited wording replaces the fact's statement, the issue's question,
    the precedent's summary or the contradiction's description, in the
    reviewed version only.
- **D6-4 Who.**
  - A new action `REVIEW_ANALYSIS` (Administrator, the lead advocate,
    associate advocates; not on archived cases), checked by the API.
  - Paralegals see review states, reviewed wording and history, but not the
    notes.
  - Clients have no access: staff routes only.
- **D6-5 Timeline.**
  - Review actions are shown on the matter timeline as entries **derived
    from the review history**. They are not stored as rows in
    `timeline_events`, so the analysis evidence builder (which reads only
    `timeline_events`) can never send them to a model.
  - Notes and finding text never appear on the timeline: only the kind, the
    id, the decision and the run date.
- **D6-6 Brief.**
  - A DOCX file generated locally on request, not stored, and with no model
    call.
  - It contains **only accepted and edited findings**, with citations:
    document name, page or part, and the verified quote, or the judgment's
    title, court, citation and year from the collection.
  - It states how many findings are unreviewed or rejected and that they are
    not included. It is never called "approved" as a whole.
  - Each item is attributed to its reviewer and date, and edited items are
    marked as lawyer wording.
  - Synthetic judgments are labelled as fictional, and sources that changed
    after the run are flagged.
  - It ends with the decision-support disclaimer. Notes and internal ids are
    left out, and the file name is sanitised.
  - Anyone who may view the case's analysis may export it.
  - With no accepted finding, the export answers 409 with the reason.
- **D6-7 Audit.**
  - `analysis.finding_reviewed` records the run, finding, status, version
    and whether the wording or note changed, but no text.
  - `analysis.brief_exported` records the run and the counts.
- **D6-8 Without migration 0012** (as Phase 5 did without 0011): the review
  routes answer 503 "migration 0012 needed", the timeline omits review
  entries, and nothing else changes.
- **D6-9 Live database.** Migration 0012 is additive (two new tables).
  Applying it to `lexflow` follows the M8 procedure: inspect the target,
  take a fresh backup, verify the restore, then upgrade. *Done on
  2026-10-25 (log B8a): the backup was restored into
  `lexflow_pre0012_verify`, live and restore were identical row for row,
  the upgrade ran from 0011 to 0012, and there were 0 unexpected
  differences afterwards.*

## 4. Acceptance criteria

| # | Criterion | Evidence required |
|---|---|---|
| AC1 | **Persistence and history.** Every decision is stored with actor and time. History is append-only and complete. The original AI result is unchanged. A finding is reviewed per run (ids are unique only within a run). Constraints prevent duplicates. Concurrent or stale writes are refused (409). Repeating a request creates no duplicate event | model and migration tests; API tests |
| AC2 | **Authorization and API.** Administrator, lead and associate may review; a paralegal may read but not review; clients and outsiders get 403 or 404; archived cases are refused; cross-case and cross-run ids are refused; invalid statuses and transitions give 422; unknown findings give 404 | API tests |
| AC3 | **Evidence isolation.** Review notes, decisions and audit records never enter the model's evidence or prompt. Review does not change completed runs' evidence | regression tests on `evidence.assemble` and `prompt.render` |
| AC4 | **Review UI.** Every finding shows its state, and **unreviewed findings are visibly marked "Unreviewed"**. A reviewer can accept, reject (with a reason), edit (keeping the original visible) and clear. Paralegals see no controls and no notes. The state changes only after the server answers. Loading, error and stale-version messages are shown. History, reviewer and time are visible. Changed sources are flagged | Vitest |
| AC5 | **Brief export.** A DOCX holding **only accepted findings** (edited ones in the lawyer's wording) with citations; the counts of unreviewed and rejected findings stated; the disclaimer; no notes; a sanitised file name; access-checked; audited; no model call | export tests that open the generated DOCX |
| AC6 | **Provenance and stale sources.** Citations come from the stored validated result. Sources changed after the run are flagged in the UI and the brief, and never replaced | export and API tests |
| AC7 | **Synthetic labels and confidentiality.** Synthetic judgments are labelled as fictional in the brief. Notes are excluded from the brief, the timeline and the audit details | export and audit tests |
| AC8 | **Regression and fresh verification.** Full backend pytest, ruff, format, mypy, alembic check, OpenAPI and API-type drift, `npm run check`, Playwright and mutation checks, all fresh and recorded | logs in `docs/verification/phase6/` |
| AC9 | **Documentation and traceability.** This plan, ADR 0020, SRS, traceability, the verification README, the log and the checkpoint agree | review at closure |
| AC10 | **Git state.** One closure commit, "Phase 6: lawyer review and case brief export", containing only Phase 6 changes; a clean tree; the brief's hash unchanged | `git` at closure |

## 5. Batches

| Batch | Deliverable | Done when |
|---|---|---|
| B0 | Preflight, plan, `CLAUDE.md`, log, checkpoint, verification README | records exist and the checkpoint validates |
| B1 | Models and migration 0012; tests | migration round trip on a scratch test database; model tests pass |
| B2 | Review service and API; audit; timeline entries | AC1 and AC2 tests pass |
| B3 | Evidence isolation | AC3 tests pass |
| B4 | Review UI | AC4 Vitest tests pass |
| B5 | Brief export (backend and UI button) | AC5–AC7 tests pass |
| B6 | Integration and edge cases; e2e | e2e review-and-export test passes |
| B7 | Full verification | AC8 |
| B8 | Records and closure commit | AC9, AC10 |

## 6. Out of scope

Phase 7 (outcome assessment, thresholds); real-judgment acquisition (a
dataset decision: it needs verified reuse terms, provenance, and separation
from the synthetic demo data and the evaluation fixtures; see Phase 5 log
M10.3); any new model call; UI redesign; local LLM.

## 7. Safety rules for this phase

- Never run tests or migrations against `lexflow` except by the D6-9
  procedure.
- The test suites use `lexflow_test` and `lexflow_e2e`, which the project's
  own setup recreates; the URL guards refuse `dbname` and `service`
  parameters.
- Make no paid or real model call.
- Never print `.env` values.
- Never change `docs/DEVELOPMENT_BRIEF.md` (SHA-256
  `274ecaed93400f51dd47c42337fbd6e101aa6be366b80d977d1522359b34c2ec`).

## 8. Verification commands

`server/`:
- `.venv\Scripts\python -m pytest -q`
- `ruff check .`, `ruff format --check .`
- `mypy`, `mypy --platform linux .`
- `python scripts/export_openapi.py --check`
- `alembic check` (test database only)

Root:
- `npm run check`
- `npx playwright test`
- `server\.venv\Scripts\python docs/verification/phase6/run_mutation_checks.py`

## 9. How to resume

Phase 6 is closed. The checkpoint's `next_action` names the next step:
Phase 7 is gated and starts only on the owner's instruction. The resume
instruction in `CLAUDE.md` still applies to any later session.

## 10. Remaining limitations and deferred items (non-blocking)

- Precedent similarities and differences are shown as the AI stated them;
  only the summary can be replaced by the lawyer's wording.
- Two first decisions written at exactly the same moment are refused by the
  unique constraint (the API answers 409). There is no dedicated concurrent
  test, because the test transaction setup cannot run truly parallel
  requests.
- Notes are stored in the local database. They are private to reviewers,
  but they are not encrypted at rest (local-only deployment, ADR 0005).
- The verification database `lexflow_pre0012_verify` and the backup
  `server/var/backups/lexflow-20261025-043125-pre-0012.dump` are kept; how
  long to keep them is the owner's decision.
- Deferred: the real judgment source (dataset phase; it needs verified
  reuse terms, provenance and separation from synthetic data); Phase 7
  thresholds (none agreed).
