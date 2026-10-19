# 0014 — The client portal: a separate API surface and explicit sharing

Status: Accepted (Phase 2b)

## Context

Clients should be able to see their own matters and the papers their advocate
chooses to give them, and nothing else: not other clients' matters, not the
firm's internal notes, not documents that were never meant for them.

## Decision

- **A Client account represents one client** (`users.client_id`; a database
  check makes a Client without a client, or anyone else with one, impossible).
- **A separate API surface:** `/api/portal/*`, mounted for Client accounts
  only. Every staff router is mounted for staff roles only. Neither side ever
  serves the other.
- **Every portal query filters on the account's own `client_id`.** The portal
  shows the client's cases that are not archived, without internal details
  (summary, priority, opposing party, team, timeline, cancelled hearings),
  scheduled hearings from today, and **only documents an advocate on the case
  has explicitly shared**. Deleting a document stops sharing it; restoring does
  not share it again. Anything else answers 404.
- **Isolation before sign-in:** Client sign-in was enabled only after tests
  proved the isolation, with sessions opened directly: a sweep of every staff
  route answers 403 to a Client, every portal route answers 403 to staff, and a
  second client can reach none of the first client's records. Each guard was
  removed in turn to check the tests fail.

## Consequences

- New staff routes are closed to clients automatically (router-level role
  check; the sweep test enumerates the OpenAPI document, so a new route is
  covered without editing the test).
- The front end keeps the two areas apart too (`/app` for staff, `/portal` for
  clients, return-to links honoured only inside the account's own area), but
  the server is what enforces it.
