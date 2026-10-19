# 0009 — TanStack Query in the front end; MSW at the network boundary in tests

Status: Accepted (Phase 1)

## Context

Moving from in-memory state to an API introduces loading, error and stale-data
states on every page, and mutations whose effects must show up on other pages
(a new document changes the case list's document count).

## Decision

- **TanStack Query** (`src/hooks/useCases.ts`) owns server state: one query per
  read endpoint with shared query keys, and mutations that invalidate the
  affected queries when they settle. No retries on 4xx responses.
- Pages handle each state explicitly with shared `LoadingState` and
  `ErrorState` (with Try again) components, and distinguish "no data yet" from
  "nothing matches the filter".
- `CasesContext` and browser-side id and case-number generation were removed.
- Tests keep using the real routes, providers and pages, and fake the API only
  **at the network boundary** with **MSW** (`src/test/mockApi.ts`): an
  in-memory fake built from the sample data that mirrors the server's shapes,
  status codes, problem codes and messages. Tests override single routes for
  failures and delays.

Rules added after the independent review of Phase 1:

- **Data on screen wins over a failed refresh.** TanStack Query keeps `data`
  when a background refetch fails; pages show it with a `StaleDataNotice` (and
  Try again) instead of replacing it with an error. Only a query that never
  loaded, or a case that no longer exists, shows the full error state.
- **An unreachable API is recognised behind the proxy.** The API always answers
  errors with a problem document, so a 5xx without one (the Vite proxy's empty
  500 when the API is down, or a gateway's 502-504) is reported as "Can't reach
  the LexFlow server", like a failed `fetch`.
- **Concurrent mutations settle through their own promise** (`mutateAsync`):
  callbacks passed to `mutate()` fire only for the latest call.

## Consequences

- The MSW fake is a second implementation of the contract and can drift from
  the server in behaviour (shapes are type-checked). The end-to-end tests
  (ADR 0010) cover the real server for the main flows.
- jsdom's `FormData` and `File` cannot be read by Node's `fetch`, so the test
  setup uses Node's own `File`, `Blob` and `FormData` globals.
