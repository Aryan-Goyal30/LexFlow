# Architecture decision records

Short records of the decisions behind Phase 1 (backend and persistence): what was
decided, why, and what it costs. The decisions were approved in the Phase 1 plan
before implementation; these records write them down with what was learned while
building them.

| No. | Decision | Status |
| --- | --- | --- |
| [0001](0001-python-fastapi-backend.md) | Python 3.12 + FastAPI backend in `server/` | Accepted |
| [0002](0002-postgresql-sqlalchemy-alembic.md) | PostgreSQL 17, SQLAlchemy 2 (sync), Alembic | Accepted |
| [0003](0003-openapi-contract-generated-types.md) | OpenAPI as the contract; generated TypeScript types; drift checks | Accepted |
| [0004](0004-rfc9457-problem-details.md) | RFC 9457 problem details for every error | Accepted |
| [0005](0005-local-only-security-model.md) | Local-only security model until authentication exists | Accepted |
| [0006](0006-local-disk-document-storage.md) | Local disk document storage behind an interface | Accepted |
| [0007](0007-server-allocated-case-numbers.md) | Server-allocated, per-year case numbers in India time | Accepted |
| [0008](0008-sample-data.md) | Sample data: deterministic ids, `is_sample`, development-only loader | Accepted |
| [0009](0009-frontend-data-layer-and-tests.md) | TanStack Query in the front end; MSW at the network boundary in tests | Accepted |
| [0010](0010-end-to-end-tests.md) | End-to-end tests on an isolated database with a restartable API | Accepted |

Format: Context, Decision, Consequences. Superseding a decision means adding a
new record and marking the old one "Superseded by NNNN", not editing history.
