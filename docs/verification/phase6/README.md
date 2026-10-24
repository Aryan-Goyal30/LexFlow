# Phase 6 verification

Evidence for Phase 6 (lawyer review and case brief export).
- Narrative and decisions: `docs/PHASE6_EXECUTION_LOG.md`.
- Plan and acceptance criteria: `docs/PHASE6_PLAN.md`.
- Machine-readable state: `checkpoint.json`, updated only through
  `update_checkpoint.py`.

**Status: Phase 6 complete** (closure commit "Phase 6: lawyer review and case brief export", parent `5302e41`).

## Resume

> Resume LexFlow Phase 6 from the latest verified checkpoint. Read CLAUDE.md, the Phase 6 plan, checkpoint and execution log; inspect Git state and the protected-file hash; reconcile actual repository state; then continue from the first incomplete task. Do not repeat completed work or discard existing changes.

## Commands

| Check | Command |
|---|---|
| Backend tests | `server: .venv\Scripts\python -m pytest -q -p no:cacheprovider` |
| Lint and format | `server: .venv\Scripts\ruff check .` and `ruff format --check .` |
| Types | `server: .venv\Scripts\mypy` and `mypy --platform linux .` |
| API contract | `server: .venv\Scripts\python scripts/export_openapi.py --check`; root: `npm run api:check` |
| Migrations | `alembic check` against the test database only |
| Front end | `npm run check` |
| End to end | `npx playwright test` (database `lexflow_e2e`, scripted provider) |
| Mutation | `server\.venv\Scripts\python docs/verification/phase6/run_mutation_checks.py` |

## Results (fresh, 2026-10-25, on the closure working tree; all exit 0)

| File | What |
|---|---|
| `pytest-full.log` | full back-end suite: **1028 passed** (980 from Phase 5 plus 48 Phase 6 tests), 0 skipped |
| `npm-check.log` | `npm run check`: lint, format, typecheck, API types, sample data, **193 Vitest tests**, build |
| `playwright.log` | end-to-end suite: **42 passed**, including the review-and-export test (scripted provider, database `lexflow_e2e`) |
| `run_mutation_checks.py`, `mutation-report.md`, `mutation-output.log` | 19 review and brief guards broken one at a time: **19 caught**; target files listed by SHA-256 |

Checks without a log file are recorded in the execution log (B7, B8a):
- ruff check and format;
- mypy, also for Linux;
- `export_openapi.py --check`;
- `alembic check` on `lexflow_test`;
- the migration of `lexflow` to 0012, done after a verified backup and
  restore check; its row-level comparison found 0 unexpected differences.

The Phase 6 tests by acceptance criterion:

| Criterion | Tests |
|---|---|
| AC1 persistence and history | `test_finding_reviews_model.py`, `test_analysis_reviews.py`, `test_migrations.py` |
| AC2 authorization and API | `test_analysis_reviews.py`, `test_review_lifecycle.py` |
| AC3 evidence isolation | `test_review_isolation.py` (with a control test) |
| AC4 review UI | `src/pages/review.test.tsx`, `e2e/analysis.spec.ts` |
| AC5–AC7 brief, provenance, synthetic labels, confidentiality | `test_case_brief.py`, `test_review_lifecycle.py`, `src/pages/review.test.tsx`, `e2e/analysis.spec.ts` |
