# 0010 — End-to-end tests on an isolated database with a restartable API

Status: Accepted (Phase 1)

## Context

Unit and component tests fake one side of the API. Persistence ("is it still
there after a reload, after a restart?") can only be shown with the real
browser, server, database and disk together. Running those tests must never
damage the developer's own data.

## Decision

- **Playwright** (`@playwright/test`, a dev dependency pinned to an exact
  version because browser builds are tied to it), Chromium only, one worker,
  tests in `e2e/`.
- Global setup runs `server/scripts/e2e.py prepare`: drop and recreate a
  separate database (default `lexflow_e2e`; the name must contain `e2e`) on the
  `DATABASE_URL` server, migrate, load the sample data, empty
  `server/var/e2e-uploads`. It then starts `e2e.py serve --run-id <random>`
  (API on port 8001) and records `{ pid, runId }`; Vite runs on port 5174 and
  proxies to it.
- **Stopping is identity-checked.** A process is only stopped when the
  operating system reports that the recorded pid is still running `e2e.py` with
  that exact run id (`/proc/<pid>/cmdline` on Linux, `Win32_Process` on
  Windows, `ps` elsewhere). A pid left by an interrupted run, and possibly
  reused by another program, is never signalled; the health endpoint is only a
  supplementary check (port busy before a start, free after a stop). The API is
  started detached, so one restarted by a test worker survives the worker until
  teardown stops it. `e2e/harness.spec.ts` covers this with decoy processes.
- Credentials stay inside the Python process: the Node side never reads or
  prints the database URL.
- One test restarts the API process and checks that the case and its file are
  still there and byte-identical.

## Consequences

- `npm run e2e` needs Docker running locally and the Chromium download once.
- The tests run in order and share a case; a failure skips the rest.
- CI runs them in their own job with a PostgreSQL service and keeps the report
  and API log when a test fails.
