# Overnight completion: execution log

Append-only record of the owner's "overnight master execution" instruction
(2026-10-25). It covers:
- Phase 6 verification;
- a **synthetic-only Phase 7 engineering demo** (off by default);
- integration, verification and documentation.

The real-world Phase 7 gate stays BLOCKED (R4, R5, R5a, R6 in
`docs/verification/post-phase6/README.md`). Checkpoint: `checkpoint.json` in
this folder.

## O0 — Preflight (2026-10-25)

- **Repository:** `C:/Projects/Claude/Legal Case Management System`, branch
  `master`, HEAD `707b002`. History: `0d6914c`, `eada4ef` (Phase 6),
  `5302e41` and earlier. No stashes, no remote.
- **Brief SHA-256:** `274ecaed…59b34c2ec`, matches.
- **Pre-existing uncommitted changes, left untouched and kept out of every
  commit in this run:** the reviewed audit corrections of the previous task
  (post-Phase-6 log F6):
  - `CLAUDE.md`;
  - `docs/phase7-prerequisites/PRIVACY_REVIEW_CHECKLIST.md`;
  - `docs/phase7-prerequisites/SOURCE_CANDIDATE_SCI_JUDGMENTS.md`;
  - `docs/verification/post-phase6/{README.md,checkpoint.json,execution-log.md}`.
- **Race regression test:** `server/tests/test_review_race.py` is tracked
  (committed in `707b002`) and collected by the suite.
- **Migrations:** head in code `0012` (`0012_finding_reviews.py`). Live
  `lexflow`: `0012`, read-only `select version_num from alembic_version`.
- **Processes:** only PostgreSQL listens (`127.0.0.1:5432`). No API, worker or
  Vite process is running.
- **Scripts:** `npm run check` (lint, format, typecheck, `api:check`,
  `sample-data:check`, vitest, build), `npm run e2e`. Backend commands as in
  `CLAUDE.md`.

Checkpoint: O0 — preflight complete; next: Milestone A (Phase 6 verification).

## A — Phase 6 verification (2026-10-25)

- **Each item maps to a test in the committed suite.** These tests passed in
  the fresh runs recorded today (post-Phase-6 V1 and F1: pytest 1029,
  Vitest 193, Playwright 42, mutation 19/19):
  - **Concurrent first decision:** `tests/test_review_race.py`, tracked and
    deterministic, observed with `pg_blocking_pids`.
  - **Stale version and retries:**
    `test_a_stale_version_is_refused_and_a_retry_adds_nothing`.
  - **Original result unchanged:**
    `test_reviewing_never_changes_the_evidence_recorded_for_the_run` and
    `test_accept_edit_reject_and_clear_keep_a_complete_history`.
  - **Roles, archive, missing, cross-case and not-ready:**
    - `test_only_the_cases_advocates_and_administrators_decide`;
    - `test_an_archived_case_can_be_read_but_not_reviewed`;
    - `test_runs_and_findings_must_belong_to_the_case`;
    - `test_review_ids_are_per_run`.
  - **Notes never in prompts, audit, timeline or brief:**
    - the 4 tests in `test_review_isolation.py`;
    - `test_decisions_are_audited_without_wording_or_notes`;
    - `test_review_actions_appear_on_the_matter_timeline_without_their_content`;
    - `test_the_brief_never_holds_notes_or_internal_ids`.
  - **DOCX opened by the tests:** `docx.Document(io.BytesIO(content))` in
    `test_case_brief.py`.
  - **UI:** `src/pages/review.test.tsx`, 13 tests.
  - **Contract:** the `api:check` and OpenAPI drift checks.
  - **Migration:** `test_migrations.py` covers the 0012 tables.
- **The UI test-count slip** in the Phase 6 checkpoint ("9 passed"; the file
  has 13) is already recorded as post-Phase-6 R9. The historical record is
  not edited.
- **No new defect was found**, so no Phase 6 code changed. The full suites
  are rerun at milestone D on the final tree.
- **Phase 7 plan written:** `docs/PHASE7_PLAN.md` (D7-1 to D7-10;
  P7-A1 to P7-A10, all "not implemented" at plan time).

Checkpoint: A — Phase 6 verified by mapping and existing fresh evidence; next: B1 (Phase 7 domain, models, migration 0013, flag).

## B1–B3 — Phase 7 backend: flag, data, generation, validation, API, brief (2026-10-25)

- **Domain and models:** assessment statuses, stances and uncertainty
  categories (`domain.py`). `OutcomeAssessment`, `OutcomeAssessmentReview`
  and `OutcomeAssessmentReviewEvent` (`models.py`).
- **Migration `0013_outcome_assessments.py`:** additive, three tables.
- **Flag:** `LEXFLOW_OUTCOME_ASSESSMENT`, default false. The settings refuse
  it unless the env is test or development and the database is a test or
  e2e one. Documented in `server/.env.example`.
- **Actions:** `run-assessment` and `review-assessment`, held by
  Administrator, lead and associate.
- **Package `lexflow/assessment/`:**
  - `inputs`: accepted findings only, passage hash check, gate;
  - `prompt`;
  - `output`: contract with no numeric field; unknown keys discarded and
    counted;
  - `validation` (`assessment-grounding-1`, strict);
  - `provider`: scripted only, so a real model is unavailable (R7);
  - `scripted`: deterministic, with planted errors;
  - `service`: generate, review and inputs-changed.
- **API `lexflow/api/assessments.py`:** 5 routes. The flag is a router
  dependency, so when it is off every route answers 404 exactly like an
  unknown route, even before the body is read. The setup gained
  `assessmentEnabled`.
- **Brief:** a separate "Outcome assessment (decision support)" section,
  only for an accepted or edited ready assessment, and only with the flag
  on. The export audit adds `assessmentIncluded` only when the flag is on;
  Phase 6's test expectation is kept for the default.
- **Tests added:**
  - `test_assessment_validation.py` (51 adversarial);
  - `test_assessments_api.py` (22);
  - `test_assessment_review_race.py` (1, run 5 times: 5 passed);
  - the 0013 migration test in `test_migrations.py`.
- **Fresh runs** (test databases only; `lexflow` untouched):
  - `pytest tests/test_migrations.py`: 6 passed, including `alembic check`
    (models match migrations);
  - `pytest -q`: **1104 passed**, exit 0. The first full run failed one
    Phase 6 audit-detail test because of the new key, which is now added
    only when the flag is on (fixed in code, the test unchanged);
  - ruff check and format, mypy (160 files) and mypy linux (173 files):
    clean;
  - `export_openapi.py` (regenerated), then `--check`: up to date;
  - `npm run api:types` regenerated `schema.gen.ts`;
  - `npm run check`: exit 0.

Checkpoint: B3 — Phase 7 backend complete and verified; next: commit B1–B3, then B4 (UI).

## B4 — Phase 7 UI (2026-10-25)

- **Types:** `src/types/ai.ts` gains aliases of the generated assessment
  schemas.
- **Service:** `aiService` gains `assessments`, `generateAssessment`,
  `reviewAssessment` and `assessmentHistory`.
- **Hooks:** `src/hooks/useAssessments.ts`:
  - it fetches only when the setup reports `assessmentEnabled`;
  - nothing is shown before the server stores it;
  - a 409 reloads the list.

  A finding review now also refreshes the run's assessment list (its
  accepted counts and "inputs changed").
- **Component:** `src/components/workspace/OutcomeAssessment.tsx`, a card
  labelled as a region. It shows:
  - the decision-support note and the demo banner (synthetic or scripted);
  - the uncertainty chip, "(a category, not a probability)";
  - the precedents, with SYNTHETIC badge, stance, verified quote and a
    judgment-passage link;
  - the reasoning with its references;
  - missing evidence and limitations;
  - removed items;
  - the insufficient and failed states;
  - "inputs changed";
  - the review controls (accept, edit summary, reject, clear) with
    reviewer-only notes and history;
  - earlier assessments.

  `AnalysisTab` renders it under a ready run, only when enabled.
- **Mock:** `src/test/mockAnalysis.ts` mirrors the assessment routes: 404
  unless enabled, the gate, roles, archive and versioned review.
- **Tests:** `src/pages/assessment.test.tsx`, 8 tests:
  - flag off: nothing shown and no request made;
  - the gate;
  - a ready assessment, labelled and synthetic;
  - insufficient and failed;
  - request error;
  - review after the server stores it;
  - stale 409;
  - paralegal read-only, no notes.
- **Fresh run:** `npm run check` exit 0: lint, format, typecheck,
  `api:check`, `sample-data:check`, **19 files and 201 tests**, build OK.

Checkpoint: B4 — Phase 7 UI complete; next: commit B4, then B5 (e2e, offline harness, mutation checks).

## B5 — e2e, offline harness, mutation checks (2026-10-25)

- **e2e app (`server/scripts/e2e.py`):** enables the demo with
  `setdefault("LEXFLOW_OUTCOME_ASSESSMENT", "true")`. This is allowed only
  because the app always uses `lexflow_e2e`, the scripted provider and
  SYNTHETIC judgments. `LEXFLOW_OUTCOME_ASSESSMENT=false` turns it off.
- **New e2e test** (`e2e/analysis.spec.ts`, serial after the Phase 6 one):
  - generate an assessment from the accepted F1 and the edited P1;
  - the labels: demo banner, category, "Supports", SYNTHETIC badge;
  - removal of the scripted double's 2 planted errors;
  - no percentage text;
  - judgment-passage link;
  - accept;
  - brief download;
  - the paralegal read-only;
  - outsider 404, client 403.
- **`npx playwright test`: 43 passed**, exit 0 (1.7 min).
- **Refactor (no behaviour change):** `service.assess(provider, inputs)`
  is now the database-free gate, call and validation path, used by the API
  and the harness. `test_assessments_api.py` and
  `test_assessment_validation.py` (73) passed after it.
- **Offline harness:**
  - `server/scripts/evaluate_assessment.py` with
    `tests/fixtures/assessment/synthetic-scenarios-v1.json`: 24 SYNTHETIC
    scenarios covering B10 items 1–11 and 16, plus the 3 of B10's
    "covered elsewhere" items mapped to named tests;
  - `--write --report-name assessment-eval-2026-10-25`: **24 of 24 as
    expected**, exit 0, written to `docs/verification/phase7/`;
  - `tests/test_assessment_evaluation.py` (2) runs it in the suite.
- **Mutation checks:** `docs/verification/phase7/run_mutation_checks.py`,
  25 guards (validation, inputs and gate, API, review, brief, flag, roles,
  UI).
  - `--dry-run`: 25 of 25 snippets found once.
  - Run: **25 of 25 caught**, every file restored, tree identical before
    and after.
  - Report and redacted log in `docs/verification/phase7/`.

Checkpoint: B5 — e2e, harness and mutation checks complete; next: commit B5, then D (full verification) and E (documentation).

- *Note:* the trailing spaces of captured pytest `E` lines and a blank last line were removed from `mutation-output.log` (whitespace only). The runner now strips line ends itself.
