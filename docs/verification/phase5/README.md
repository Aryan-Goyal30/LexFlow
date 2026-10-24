# Phase 5 verification

Evidence for Phase 5 (AI case analysis with Google Gemini). Narrative and
decisions: `docs/PHASE5_EXECUTION_LOG.md`. Machine-readable state:
`checkpoint.json`. Decision record: `docs/adr/0019-ai-case-analysis.md`.
Status: M1–M8 recorded; M9 stabilisation implemented and verified but not
yet committed (see `checkpoint.json`).

## M9 — stabilisation (2026-10-24/25), on the uncommitted working tree

| File | What |
|---|---|
| `pytest-full-m9-review-fixes.log` | full back-end suite after the M9 review fixes (2026-10-25): 950 passed, exit 0 — the latest run |
| `pytest-full-m9.log` | full back-end suite at the end of M9 (2026-10-24): 906 passed, exit 0 |
| `npm-check-m9.log` | `npm run check` at the end of M9: lint, format, typecheck, API types, sample data, 178 Vitest tests, build; exit 0 (the review fixes changed no front-end file) |
| `playwright-m9.log` | end-to-end suite at the end of M9: 41 passed, exit 0 (scripted provider, database `lexflow_e2e`) |
| `mutation-report-working-tree.md`, `mutation-output-working-tree.log` | `run_mutation_checks.py --working-tree`: 61 guards (40 from M7 plus 21 for M9); 61 caught; target files listed by SHA-256 |
| `analysis-eval.md`, `analysis-eval.json` | offline evaluation of validation and error handling on SYNTHETIC scenarios (`server/scripts/evaluate_analysis.py --write`); the latest report is from the review fixes: 71 scenarios, 71 as expected, validator `grounding-3`. It has no pass mark and does **not** measure the legal accuracy of any model. |

Commands, exit codes and the checks without a log file (ruff, mypy, OpenAPI
drift, `alembic check` on the test database) are recorded in the execution
log, sections M9.8 and M9.10.

## M7 — implementation verification (2026-10-20), historical

| File | What |
|---|---|
| `pytest-full.log` | ruff, format, mypy (Windows and Linux), OpenAPI drift check and the full back-end suite on the M7 code: 807 passed |
| `npm-check.log` | `npm run check`: lint, format, typecheck, API types, sample data, 176 Vitest tests, build |
| `playwright.log` | end-to-end suite: 41 passed (3 for AI analysis, with the scripted provider through the real worker) |
| `run_mutation_checks.py`, `mutation-report.md`, `mutation-output.log` | 40 guards broken one at a time (validation, parsing, provider, configuration, evidence, runs, UI); 40 caught |

## Gemini calls and the live database

- **Automated checks never contact Google.** Every test uses a fake SDK client
  or the scripted test double (labelled "not AI"), building a real Gemini
  client fails in every test, the e2e suite forces the scripted provider, and
  the offline evaluation refuses to build a real client.
- **Real Gemini calls were made by the owner**, outside the automated checks,
  from the UI on the sample case LF-2026-0361:
  - M8e, 2026-10-20: four runs and seven `generateContent` requests
    (3 × 503, 3 × 400, 1 × 200). Run `4fc9ab87` succeeded.
  - Three more runs, `1712d02e`, `5aa4711d` and `ea18be07`, all ready. These
    are recorded in log M9.0, as observed read-only on 2026-10-20.
  - Neither of these was re-queried for this README.
- **Migration 0011 is applied to the live database `lexflow`.** It was applied
  on 2026-10-20 after a fresh backup and an isolated restore check (log M8c,
  M8d), and `alembic current` was verified as 0011 (head). That is the
  recorded state; this README did not query the database. Before that, it was
  rehearsed on scratch databases only (M8a).
- Logs are redacted (home paths, database role names, row ids). The only
  key-like string in them is the fake test key `AIzaFAKE-…-not-real`.
