# 0002 — PostgreSQL 17, SQLAlchemy 2 (sync), Alembic

Status: Accepted (Phase 1)

## Context

Cases, hearings, timeline events and document records are relational and need
integrity (a document belongs to exactly one case; a case number is unique).
Later phases may need full-text search and vector search, which PostgreSQL
offers in-database (pgvector is out of scope for Phase 1).

## Decision

- **PostgreSQL 17**, run locally with Docker Compose (`server/compose.yaml`),
  bound to `127.0.0.1` only, data in a named volume.
- **SQLAlchemy 2.0** with synchronous sessions and the psycopg 3 driver. FastAPI
  runs sync endpoints in a thread pool, which is ample for one user; sync code is
  simpler to test and reason about.
- **Alembic** migrations; the tests build the schema through the real
  migrations and fail if models and migrations disagree.
- **UUID primary keys**, so ids can't be guessed or enumerated from the URL.
- The database enforces the rules it can: check constraints on status,
  priority, practice area, text lengths, the case-number format and file
  metadata; a case-insensitive unique document name per case; `RESTRICT` on
  deleting a client or advocate with cases.

## Consequences

- Developers need Docker Desktop. The README covers Windows setup.
- Tests run against a real PostgreSQL (database name must contain `test`), each
  test inside a savepoint that is rolled back; concurrency tests commit for real
  and clean up afterwards.
- Updates lock the row (`SELECT … FOR UPDATE`) so two simultaneous edits can't
  both write their "changed from X to Y" timeline entry from the same old value.
