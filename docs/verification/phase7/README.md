# Phase 7 verification — outcome assessment (synthetic engineering demo)

Fresh runs on 2026-10-25, on the final working tree of the Phase 7 commits
(test databases only: `lexflow_test`, `lexflow_migration_test`, `lexflow_e2e`;
the live `lexflow` was neither connected to by the tests nor migrated). Plan
and acceptance criteria: `docs/PHASE7_PLAN.md`. Decision:
`docs/adr/0021-outcome-assessment-demo.md`. Work log:
`docs/verification/overnight-completion/execution-log.md`.

**What this verifies:** that LexFlow's outcome-assessment workflow behaves as
specified on SYNTHETIC data:
- the flag;
- the evidence gate;
- strict validation;
- review;
- the brief;
- access;
- audit.

**What it does not verify:** legal accuracy. The scenarios are invented and
not lawyer-labelled, the provider is scripted (not AI), and the judgments are
fictional. The real-world Phase 7 gate is **BLOCKED** (R4, R5, R5a, R6, R7 in
`docs/verification/post-phase6/README.md`).

| Check | Command | Result | Exit | Evidence |
|---|---|---|---|---|
| Backend tests | `server: python -m pytest -q -p no:cacheprovider` | **1106 passed** | 0 | `pytest-full.log` |
| Lint, format, types, contract, migrations | `ruff check .`, `ruff format --check .`, `mypy`, `mypy --platform linux .`, `export_openapi.py --check`, `alembic check` (lexflow_test) | all clean | 0 each | `static-checks.log` |
| Front end | `npm run check` (lint, format, typecheck, `api:check`, `sample-data:check`, Vitest, build) | **19 files, 201 tests passed**, build OK | 0 | `npm-check.log` |
| End to end | `npx playwright test` | **43 passed**, including the Phase 7 demo journey | 0 | `playwright.log` |
| Offline assessment scenarios | `scripts/evaluate_assessment.py --write --report-name assessment-eval-2026-10-25` | **24 of 24 as expected** | 0 | `assessment-eval-2026-10-25.md` / `.json` |
| Phase 7 mutation checks | `docs/verification/phase7/run_mutation_checks.py` | **25 of 25 caught**, files restored | 0 | `mutation-report.md`, `mutation-output.log` |
| Phase 6 mutation recheck (code touched by Phase 7) | the Phase 6 runner, output redirected here | **19 of 19 caught** | 0 | `phase6-mutation-recheck/` |
| Assessment review race (simultaneous first decisions) | `tests/test_assessment_review_race.py` | 5 of 5 standalone runs passed, plus every full run | 0 | log B1–B3 |

**Not verified:**
- No manual browser session was run. The user journeys were checked by the
  automated Playwright and Vitest tests listed in the log (milestone C).
- No CI run: the repository has no remote.
- No real model and no real judgment were used.

## Acceptance (P7-A1 to P7-A10)

See the table in `docs/PHASE7_PLAN.md` §3. **Synthetic demo: P7-A1 to P7-A10
implemented and verified. Real-world gate: blocked by missing external
evidence and approval.**
