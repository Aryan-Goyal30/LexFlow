# Architecture decision records

Short records of the decisions behind Phases 1 and 2: what was decided, why,
and what it costs. The decisions were approved in the Phase 1 plan
before implementation; these records write them down with what was learned while
building them.

| No. | Decision | Status |
| --- | --- | --- |
| [0001](0001-python-fastapi-backend.md) | Python 3.12 + FastAPI backend in `server/` | Accepted |
| [0002](0002-postgresql-sqlalchemy-alembic.md) | PostgreSQL 17, SQLAlchemy 2 (sync), Alembic | Accepted |
| [0003](0003-openapi-contract-generated-types.md) | OpenAPI as the contract; generated TypeScript types; drift checks | Accepted |
| [0004](0004-rfc9457-problem-details.md) | RFC 9457 problem details for every error | Accepted |
| [0005](0005-local-only-security-model.md) | Local-only security model until authentication exists | Superseded in part by 0011 |
| [0006](0006-local-disk-document-storage.md) | Local disk document storage behind an interface | Accepted |
| [0007](0007-server-allocated-case-numbers.md) | Server-allocated, per-year case numbers in India time | Accepted |
| [0008](0008-sample-data.md) | Sample data: deterministic ids, `is_sample`, development-only loader | Accepted |
| [0009](0009-frontend-data-layer-and-tests.md) | TanStack Query in the front end; MSW at the network boundary in tests | Accepted |
| [0010](0010-end-to-end-tests.md) | End-to-end tests on an isolated database with a restartable API | Accepted |
| [0011](0011-sessions-passwords-and-csrf.md) | Server-side sessions, Argon2id passwords, CSRF and Origin checks | Accepted |
| [0012](0012-case-scoped-authorization-and-audit.md) | Case-scoped authorization, field-level rules and the audit log | Accepted |
| [0013](0013-nothing-is-deleted-in-the-app.md) | Archive, cancel, soft delete; purge only by a guarded command | Accepted |
| [0014](0014-client-portal-isolation.md) | Client portal: a separate API surface and explicit sharing | Accepted |
| [0015](0015-document-processing-worker.md) | Text extraction in a separate, database-backed worker; page-aware chunks | Accepted |
| [0016](0016-embeddings-local-and-gated.md) | Embeddings: off by default, local only, gated on a compatible pgvector image | Superseded in part by 0017 |
| [0017](0017-pgvector-trixie-and-local-embeddings.md) | pgvector on Debian 13 (`pg17-trixie`), local `bge-small-en-v1.5`, per-case search | Accepted |
| [0018](0018-judgment-collection-and-search.md) | Judgment collection: operator imports with provenance, synthetic data fenced off, staff-wide search | Accepted |

Format: Context, Decision, Consequences. Superseding a decision means adding a
new record and marking the old one "Superseded by NNNN", not editing history.
