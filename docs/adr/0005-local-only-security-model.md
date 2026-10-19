# 0005 — Local-only security model until authentication exists

Status: Accepted (Phase 1). To be revisited in Phase 2 (real authentication).

## Context

Real authentication is out of scope for Phase 1, yet the API can read, change
and delete case data and files. An unauthenticated API on a developer's machine
can still be attacked through the developer's own browser: a malicious web page
can send cross-site requests to `localhost`, or use DNS rebinding to make its
own host name resolve to `127.0.0.1` and read responses.

## Decision

- **Loopback only.** The API binds to `127.0.0.1`; `python -m lexflow` exits if
  configured with any other host. PostgreSQL is also bound to `127.0.0.1`.
- **Host allow-list** (`LocalOnlyMiddleware`): requests whose `Host` is not
  `localhost`, `127.0.0.1` or `::1` get 400 `invalid-host`. This defeats DNS
  rebinding, where the browser sends the attacker's host name.
- **Origin check on writes:** `POST`, `PUT`, `PATCH` and `DELETE` with an
  `Origin` that is not a loopback origin (or is `null`) get 403
  `forbidden-origin`. This blocks cross-site form posts and `fetch` calls.
- **No CORS.** The browser reaches the API through the Vite proxy on the same
  origin, so no cross-origin access is ever granted.
- Defence in depth for files and errors: see ADRs 0004 and 0006.

## Consequences

- These measures protect a single developer's machine. They are **not** access
  control: any local process can use the API. The README says so prominently,
  and the app must not be deployed or exposed before Phase 2.
- The Host and Origin checks and the loopback-only start-up refusal (`0.0.0.0`,
  `::`, LAN addresses and host names are refused before a server starts) have
  tests, and each was checked to fail when its protection is removed.
