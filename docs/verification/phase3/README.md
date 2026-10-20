# Phase 3 final verification (2026-10-20)

Run against commit `c12d248` with a clean working tree (`git status` empty
before the run; no tracked file changed by it). This closes the gaps left by
the post-Phase-3 acceptance audit: full suites on the exact committed tree, and
mutation checks with saved output.

## Results

| Check | Command | Result | Saved output |
|---|---|---|---|
| Back end, full | `server\.venv\Scripts\python -m pytest -q -p no:cacheprovider` (in `server/`) | **589 passed**, 0 failed | `pytest-full.log` |
| End to end (real API + worker) | `npx playwright test` | **32 passed**, 0 failed; afterwards no `e2e.py` processes, port 8001 free | `playwright.log` |
| Mutation checks | `server\.venv\Scripts\python -B docs/verification/phase3/run_mutation_checks.py` | **14 of 14 caught**; every file restored byte-for-byte | `mutation-report.md`, `mutation-output.log` |

Each mutation failed on test assertions (the failing tests are listed in
`mutation-report.md`), not on import or collection errors. The runner was run
three times (twice to strip terminal colour codes and fix style in the report
script); all three runs caught 14 of 14.

The intermittent failure of
`tests/test_auth_committed.py::test_failures_and_lockout_survive_the_failed_requests`
(seen once during P3-M2) did **not** recur: it passed in this full run. Its
cause remains unexplained.

## Safety evidence

- **Databases used** (checked before running): pytest `lexflow_test` (from
  `server/.env` `TEST_DATABASE_URL`; the conftest refuses names without "test"
  and points `DATABASE_URL` at it before the app loads) and the migration
  tests' scratch `lexflow_migration_test` (created and dropped by the test,
  same guard); Playwright `lexflow_e2e` (`scripts/e2e.py` refuses names without
  "e2e"). No `TEST_DATABASE_URL`/`DATABASE_URL` override in the shell.
- **`lexflow` untouched:** a read-only fingerprint of every table (columns, row
  count, md5 of all rows) before and after the run is identical (14 tables,
  revision 0008).
- The running development API has no auto-reload, and the development queue
  was empty, so the temporary source edits of the mutation checks were never
  loaded by anything serving `lexflow`.
- Database image `postgres:17` and volume `lexflow_pgdata` unchanged; no
  container removed; embeddings still disabled; no model downloaded; the two
  older PDFs not queued; scratch databases kept.
- `docs/DEVELOPMENT_BRIEF.md` SHA-256 still starts `274ecaed93400f51`.
- The saved logs contain no credentials (the word "password" appears only in
  e2e test titles). In `mutation-output.log`, local home paths, the database
  role name (the password was already masked) and the ids of rows created by
  the tests in the throwaway test database are replaced by `<home>`, `<user>`
  and `<uuid>`; the runner applies the same redaction on every run.

## Still open

- Embeddings (pgvector image decision) and the Phase 4 prerequisites, as in
  `docs/PHASE3_EXECUTION_LOG.md` and `docs/PHASE4_PLAN.md`.
- The unexplained one-off lockout-test failure (not reproduced).
