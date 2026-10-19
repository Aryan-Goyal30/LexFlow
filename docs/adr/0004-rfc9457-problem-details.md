# 0004 — RFC 9457 problem details for every error

Status: Accepted (Phase 1)

## Context

The front end must show useful messages (beside the right form field, or for the
right file) without parsing free text, and errors must never leak internals such
as stack traces, SQL or parameter values.

## Decision

Every error response, including framework errors (404 route, 405, malformed
JSON, oversized body, unexpected exceptions), is an RFC 9457 problem document
(`application/problem+json`) with:

- `type`, `title`, `status`, `detail` (a sentence a user can read);
- a stable `code` (`validation-error`, `case-not-found`, `duplicate`,
  `content-mismatch`, `too-large`, `forbidden-origin`, …) for the UI to branch on;
- `errors`: field errors as `{field, message}`, using the camelCase field names
  and the same wording as the front end's own validation.

Unexpected exceptions return a generic 500 and are logged with their type and
stack frames only, never the message (which can contain user data or SQL);
the database engine hides bound parameters.

## Consequences

- `ApiError` (`src/services/api/client.ts`) exposes `status`, `code` and
  `fieldErrors`; the new-case form maps field errors to its inputs.
- Tests assert on codes and messages, so wording changes are deliberate.
