# 0008 — Sample data: deterministic ids, `is_sample`, development-only loader

Status: Accepted (Phase 1)

## Context

The prototype's fictional sample cases are useful for demonstrations, but they
must never be mistaken for real matters, never be loaded into a real database by
accident, and must not be invented anew on the server (no fabricated legal data).

## Decision

- The front end's `src/data/mockData.ts` stays the single source. A script
  exports it to `server/lexflow/seed/sample_data.json`; `npm run
  sample-data:check` fails if they differ.
- `python -m lexflow.seed` loads it **only when `LEXFLOW_ENV=development`**
  (the default environment is `production`). Loading is idempotent
  (`ON CONFLICT DO NOTHING`), with **deterministic UUIDs** (UUIDv5 in a fixed
  namespace) so reloading never duplicates rows.
- Every sample row has `is_sample = true`; the API returns `isSample` and the UI
  shows a **Sample** badge. Sample documents have no stored file and say so.
- The case-number counters are moved past the sample numbers when loading.

## Consequences

- Runtime case data comes only from the API; `mockData.ts` is used at runtime
  only for the simulated signed-in user (Phase 2 replaces it).
- Front-end tests build their fake API from the same sample data.
