# 0011 — Server-side sessions, Argon2id passwords, CSRF and Origin checks

Status: Accepted (Phase 2). Supersedes the "until authentication exists" parts of 0005.

## Context

Phase 2 gives LexFlow real accounts. The app is a single-origin web app (Vite
serves it; the API sits behind the same origin), it holds confidential case
material, and sessions must be revocable: when an account is disabled or its
password changes, access has to end at once.

## Decision

- **Accounts are provisioned, never self-registered.** The first Administrator
  is created with `python -m lexflow.cli.users`; later accounts with the same
  command or the Administration screen. New and reset accounts get a temporary
  password the person must replace at first sign-in (it also expires, after
  `LEXFLOW_TEMPORARY_PASSWORD_HOURS`).
- **Opaque server-side sessions** rather than JWTs: a 256-bit random token
  (`secrets.token_urlsafe(32)`) in an `HttpOnly`, `SameSite=Strict` cookie
  (`__Host-` prefixed and `Secure` when `LEXFLOW_COOKIE_SECURE=true`, which
  production requires). Only the token's SHA-256 digest is stored. Sessions end
  after 30 minutes idle or 12 hours in any case, on sign-out, on a password
  change (a fresh token is issued to the person who changed it) and when an
  account is disabled.
- **Argon2id** password hashes (argon2-cffi), rehashed when parameters change;
  12 to 128 characters, not only spaces, not the e-mail address or name (NIST
  SP 800-63B: length over composition rules).
- **Lockout:** the 5th consecutive failure locks the account for 15 minutes;
  every refusal gives the same generic answer, and failures are counted and
  audited in an independent transaction so a failing request cannot roll them
  back.
- **CSRF:** every change needs the `X-LexFlow-Request: 1` header (a simple form
  or a cross-site `fetch` without CORS cannot add it), an exact `Origin` from
  `LEXFLOW_ALLOWED_ORIGINS`, and the Strict cookie. A request carrying the
  session cookie but no `Origin` is refused. The dev server grants no CORS.
- **Deny by default:** a gate rejects unauthenticated requests to anything but
  health, sign-in and sign-out before a body is read; routers also require a
  signed-in user (and the right role), so a forgotten check on one route does
  not open it. The loopback-only binding and Host allow-list of 0005 remain.

## Consequences

- No passwords on command lines (hidden prompt or `--password-stdin`), in logs,
  in API responses or in the audit log; tests check each.
- Sessions need a database lookup per request (cheap at this scale) and stale
  rows are purged on sign-in.
- Production start-up refuses a non-loopback host, cookies without `Secure`,
  and sample accounts that can sign in. Deployment itself (HTTPS, a reverse
  proxy) is still out of scope.
