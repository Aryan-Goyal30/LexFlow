# 0007 — Server-allocated, per-year case numbers in India time

Status: Accepted (Phase 1)

## Context

Before Phase 1 the browser computed the next case number from the cases it had
loaded, which breaks as soon as two people (or two tabs) create cases. Case
numbers have the form `LF-<year>-<sequence>`, and "the year" and "today" must
not depend on the server's or browser's time zone.

## Decision

- The server allocates case numbers from a `case_number_counter` table, one row
  per year, with a single atomic `INSERT … ON CONFLICT DO UPDATE … RETURNING`.
  A year's first counter starts after the highest number already in use, so
  imported or sample cases are never duplicated.
- The sequence is zero-padded to at least four digits and may grow beyond.
- "Today" for date rules (a next hearing cannot be in the past) and the year
  come from `LEXFLOW_TIMEZONE`, default `Asia/Kolkata`.
- A check constraint enforces the format and a unique index the uniqueness.

## Consequences

- Concurrent creation is safe; a test creates cases from parallel threads
  through the API and checks that no number repeats.
- The counter update is part of the case's own transaction, so a create that
  fails and rolls back does not use up a number. Concurrent creates in the same
  year queue briefly on the counter row.
