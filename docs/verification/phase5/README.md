# Phase 5 verification

Evidence for Phase 5 (AI case analysis with Google Gemini). Narrative and
decisions: `docs/PHASE5_EXECUTION_LOG.md`. Machine-readable state:
`checkpoint.json`. Decision record: `docs/adr/0019-ai-case-analysis.md`.

| File | What |
|---|---|
| `pytest-full.log` | ruff, format, mypy (Windows and Linux), OpenAPI drift check and the full back-end suite on the final code: 807 passed |
| `npm-check.log` | `npm run check`: lint, format, typecheck, API types, sample data, 176 Vitest tests, build |
| `playwright.log` | end-to-end suite: 41 passed (3 for AI analysis, with the scripted provider through the real worker) |
| `run_mutation_checks.py`, `mutation-report.md`, `mutation-output.log` | 40 guards broken one at a time (validation, parsing, provider, configuration, evidence, runs, UI); 40 caught |

No test contacts Google: the provider is a fake SDK client or the scripted
test double (labelled "not AI"), and building a real Gemini client fails in
every test. No Gemini call was made during Phase 5. Logs are redacted (home
paths, database role names, row ids).

Migration 0011 was rehearsed on scratch databases only (an empty scratch
database, and a restore of a fresh dump of the live database); it is **not**
applied to the live database (owner-gated, M8).
