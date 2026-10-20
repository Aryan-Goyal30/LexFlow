# Phase 4 verification

Evidence for Phase 4 (judgment collection and retrieval). Narrative and
decisions: `docs/PHASE4_EXECUTION_LOG.md`. Machine-readable state:
`checkpoint.json`.

| File | What |
|---|---|
| `pytest-full.log` | full back-end suite on the final code: 705 passed |
| `npm-check.log` | `npm run check`: lint, format, typecheck, API types, 169 tests, build |
| `playwright.log` | end-to-end suite: 38 passed (6 for research and the library) |
| `run_mutation_checks.py`, `mutation-report.md`, `mutation-output.log` | 19 guards broken one at a time; 19 caught |
| `judgment-eval.json`, `judgment-eval.md` | SYNTHETIC engineering evaluation (keyword, semantic, hybrid) |

The evaluation corpus and labels are invented: they test the machinery, not
legal research quality. No real judgment source has been approved; the live
collection is empty.
