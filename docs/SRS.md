# LexFlow — Software Requirements Specification

Version: Phase 4 (2026-10-20). Describes the system **as built** through
Phase 4 and marks what later phases add. Source of the plan:
`docs/DEVELOPMENT_BRIEF.md`. Traceability to code and tests:
`docs/TRACEABILITY.md`. Architecture and UML: `docs/ARCHITECTURE.md`.

## 1. Purpose and scope

LexFlow is a legal case workspace and research assistant for advocates in the
Indian legal system. It manages cases, hearings, clients and documents,
extracts and searches document text, and keeps a searchable collection of
judgments. AI analysis (Phase 5), lawyer review of AI findings (Phase 6) and
outcome assessment (Phase 7) are **not** part of this version. Any AI is
decision support only; LexFlow never replaces the lawyer or the judge.

## 2. Users and roles

| Role | Scope |
|---|---|
| Administrator | Everything; accounts; audit log; archiving |
| Advocate | Cases they lead or are on the team of; opens cases |
| Paralegal | Cases they are assigned to; limited edits |
| Client | The client portal only: own matters, shared documents |
| Operator | Command line on the server: provisioning, purges, imports, model download |

## 3. Functional requirements

Status: **Done** = implemented and tested; **Later** = a future phase.

| Id | Requirement | Status |
|---|---|---|
| FR-1 | Sign in with accounts created by an Administrator; lockout after 5 failures; session expiry | Done (Phase 2) |
| FR-2 | Four roles enforced on the server; inaccessible cases answer "not found" | Done (Phase 2) |
| FR-3 | Create, view, edit and archive cases; server-allocated case numbers | Done (Phases 1–2) |
| FR-4 | Every case change recorded on its timeline with who and when | Done (Phase 2) |
| FR-5 | Case teams (associates, paralegals) managed by the lead or Administrator | Done (Phase 2b) |
| FR-6 | Schedule, change and cancel hearings; firm-wide hearing view | Done (Phases 1–2b) |
| FR-7 | Manage clients | Done (Phases 1–2b) |
| FR-8 | Upload, download, soft-delete, restore and share documents; guarded purge | Done (Phases 1–2b) |
| FR-9 | Client portal: own matters, coming hearings, shared documents only | Done (Phase 2b) |
| FR-10 | Background text extraction of PDF/DOCX/TXT with visible status and reasons | Done (Phase 3) |
| FR-11 | Page-aware text and chunks; read a document's text page by page | Done (Phase 3) |
| FR-12 | Optional local embeddings; case search by keyword, meaning or both (API) | Done (Phase 3) |
| FR-13 | Import judgments with source, terms-of-use record and metadata; duplicates detected | Done (Phase 4) |
| FR-14 | Search judgments by keyword, meaning or hybrid; each result with citation, court, date, passage, page and source | Done (Phase 4) |
| FR-15 | Research tab in each case connected to judgment search | Done (Phase 4) |
| FR-16 | Precedent Library: browse, filter, search and read judgments with their source | Done (Phase 4) |
| FR-17 | Reproducible search evaluation (Recall@K, Precision@K, MRR) | Done (machinery, Phase 4); real-corpus evaluation pending external data |
| FR-18 | AI case analysis with validated citations | Later (Phase 5) |
| FR-19 | Lawyer review of AI findings; brief export | Later (Phase 6) |
| FR-20 | Gated outcome assessment | Later (Phase 7) |

## 4. Non-functional requirements

| Id | Requirement | How it is met |
|---|---|---|
| NFR-1 Security | Deny by default; sessions in `HttpOnly` cookies; CSRF header + origin checks; Argon2id | Session gate, staff/portal routers, `lexflow/authz.py` |
| NFR-2 Privacy | No client document leaves the machine unless configured; embeddings local | Local model, no hosted AI; worker never downloads |
| NFR-3 Auditability | Sign-ins, refusals, changes and reads recorded; append-only | `audit_events` + database trigger; searches audited without query text |
| NFR-4 Integrity | Nothing destroyed in the app; migrations rehearsed before live use | Soft delete, archive; backup/restore/rehearsal procedure in the logs |
| NFR-5 Resource limits | Upload 25 MB; extraction 120 s / 1,000 pages / 5 MB text; search ≤ 300 characters, ≤ 100 ranked judgments | Settings in `lexflow/config.py`; API validation |
| NFR-6 Honesty | No simulated AI; synthetic data labelled and fenced off | "Not connected" AI tabs; synthetic gates and badges |
| NFR-7 Maintainability | Typed end to end; one OpenAPI contract; drift checks | mypy, TypeScript strict, `npm run api:check` |
| NFR-8 Testability | Automated back-end, front-end, end-to-end and mutation checks | pytest, Vitest, Playwright, mutation runners |
| NFR-9 Accessibility | Labelled controls, keyboard use, visible focus, phone widths | Component conventions; e2e keyboard and 375 px checks |

## 5. Constraints and assumptions

- Local deployment on one machine (`127.0.0.1`); not reviewed for internet
  deployment.
- PostgreSQL 17 with pgvector (`pgvector/pgvector:pg17-trixie`).
- Judgment sources must be lawfully usable; LexFlow records but does not
  decide the terms. **No real source is approved yet**, so the live
  collection is empty.
- The embedding model is English-only.

## 6. Out of scope (this version)

OCR; hosted AI; crawling or downloading judgments; outcome prediction;
e-mail; multi-factor sign-in; internet deployment.
