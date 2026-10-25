# LexFlow — Legal Case Workspace & Research Assistant

**Status (2026-10-25):** Phases 1–6 implemented and verified locally (accounts,
roles, cases, documents and text, judgment research, AI case analysis, lawyer
review and a DOCX case brief). **Phase 7 (outcome assessment) is implemented only
as a synthetic-data engineering demonstration, off by default;** its real-world
use is blocked (see [Limitations](#limitations)). For a guided tour, see
[`docs/DEMO_GUIDE.md`](docs/DEMO_GUIDE.md).

LexFlow helps a law firm work its active cases. Each case has its own
**workspace** where the team manages the case record, its hearings and the case
papers. Clients follow their own matters in a separate **client portal**.
Precedent research searches the firm's judgment collection, and an optional AI
case analysis (Google Gemini, configured by the owner; off by default) proposes
facts, issues, precedent comparisons and contradictions, each checked against
its source before it is shown. A lawyer then reviews every finding.

The intended workflow:

**create or open a case → manage case information → upload documents →
analyse the case → research precedents → review the analysis**

All steps work and are **saved** in PostgreSQL (files on the local disk) behind
a FastAPI server, with real sign-in and role-based access. Two inputs are
external and not provided: **no real judgment source is approved** (only
labelled SYNTHETIC judgments exist), and analysing **real client material**
needs a privacy review first (only sample cases may be analysed).

The sample data is set in an **Indian legal context** (Supreme Court of India,
High Courts, District & Sessions Courts; "Advocate" terminology). All people,
organisations and matters in it are fictional, and the app labels them
**Sample**.

`docs/DEVELOPMENT_BRIEF.md` is the source of truth for the product direction
and the phased roadmap. `docs/PHASE1_EXECUTION_LOG.md` and
`docs/PHASE2_EXECUTION_LOG.md` record how each phase was built and verified,
and `docs/adr/` records the main decisions.

> **Local use only.** LexFlow now has real accounts, sessions and access
> control, but it has not been reviewed for deployment: the API refuses to
> listen on anything but `127.0.0.1`. Do not expose it to a network or put real
> client data in it.

---

## What works

### Accounts and roles

- **Sign-in** with accounts created by an Administrator (no self-registration),
  from the Administration screen or the command line. A temporary password must
  be replaced at first sign-in. Five wrong passwords in a row lock an account
  for 15 minutes. Sessions end after 30 minutes idle, 12 hours, sign-out, a
  password change or when the account is disabled.
- **Four roles.** *Administrators* see and manage everything. *Advocates* see
  the cases they lead or are on the team of. *Paralegals* see the cases they are
  assigned to and may change only the court and the opposing party. *Clients*
  use the client portal only. The screens offer only what the server allows;
  the server checks everything again, and a case you may not see is "not found".

### Cases (staff)

- **Case list** (`/app/cases`): search, status filters, next hearing and
  document count; archived cases on request ("Show archived").
- **New case**, for Administrators and Advocates (an Advocate leads the cases
  they open). The server allocates the case number (`LF-<year>-<sequence>`).
- **Case workspace** (`/app/cases/:caseId`) with Overview, Documents, AI
  Analysis and Research tabs (the tab is in the URL).
- **Editing** (`/app/cases/:caseId/edit`): only the fields you may change are
  shown, and only changed fields are sent. **Status** changes, and changes of
  lead or client (Administrators), are recorded on the timeline with the person
  and the time.
- **Case team:** the Administrator or the lead adds or removes associate
  advocates and paralegals; access follows at once.
- **Archiving** (Administrators): the case is kept in full, read-only and out of
  the default list until restored.
- **Hearings:** anyone on the case schedules, changes and cancels hearings.
  Cancelled hearings stay listed with the reason but never count as the next
  hearing.
- **Documents:** upload PDF, Word, text and images (up to 25 MB; the server
  checks that the contents match the type), open, and remove. Removing is
  **soft**: the Administrator or lead can restore it from "Deleted Documents";
  only an operator command removes files for good. Advocates **share** documents
  with the client explicitly.
- **Document text** (Phase 3): each upload is queued and a separate worker
  extracts its text (PDF text layer page by page, Word body and tables, plain
  text). The Documents tab shows the status (waiting, extracting, extracted with
  the page count, or failed with the reason) and refreshes itself; staff on the
  case open **View text** page by page, and those who may upload can **try
  again**. Scans fail honestly ("no text layer": there is no OCR). Clients never
  see extracted text.
- **Case search (API only):** `GET /api/cases/{id}/search` finds passages in a
  case's documents by keywords, or by meaning with optional **local
  embeddings** (`BAAI/bge-small-en-v1.5` on this computer, off by default;
  `server/README.md`). Results are the case's own passages with page and
  position, for staff who may view the case. There is no search screen yet.

### Firm-wide pages

- **Hearings** (`/app/hearings`): every hearing on your cases by day, with
  presets (next 7 or 30 days, past 30 days), custom dates and cancelled ones on
  request.
- **Clients** (`/app/clients`): the clients of your cases (all, for
  Administrators), with contact details and their cases; Administrators and
  Advocates add clients, and those on a client's cases edit them.
- **Practice Overview** (`/app/dashboard`): counts, recent cases, upcoming
  hearings.
- **Administration** (Administrators): **Accounts** (create, edit, temporary
  passwords, unlock, disable/enable) and the **Audit log** (who did what and
  when, with filters). The log cannot be changed through LexFlow and the
  database rejects edits, but it is **not tamper-proof** against someone with
  database administrator access.

### Client portal (`/portal`)

A Client account sees its own matters (not archived ones), their coming
hearings and **only the documents an advocate shared**, with downloads. No
internal notes, priority, team or timeline. Staff never see the portal and
clients never reach the staff app.

### Judgments: Research and the Precedent Library (Phase 4)

- **Precedent Library** (`/app/precedents`) for all staff: browse the firm's
  judgment collection newest first, filter by court and year, search, and open
  a judgment (`/app/precedents/:id`) to read it page by page with its
  **source and the terms-of-use record** of that source.
- **Research tab** in each case: the same search. Results show the matching
  passage with its page, court, date and citation, a link to the full
  judgment and one to the source. Keyword search always works; searching by
  meaning (semantic, hybrid) needs the optional local embeddings and is
  otherwise shown as unavailable, with the reason.
- **Judgments are imported only by an operator** from files and a manifest
  that records their source and its terms of use
  (`python -m lexflow.cli.judgments import`, preview first;
  `server/README.md`). LexFlow never downloads judgments. **No source has
  been approved yet**: the development collection holds only three judgments
  labelled "SYNTHETIC DEMO — NOT REAL CASE LAW", imported for a
  demonstration. The other invented test judgments exist only in test
  databases. Every synthetic judgment is labelled wherever it appears.
- Results are ranked passages of stored judgments, not legal conclusions.

### AI analysis, lawyer review and outcome assessment (Phases 5–7)

- **AI case analysis** (AI Analysis tab; Phase 5): the Administrator and the
  case's advocates choose documents, confirm what is sent, and start a run. A
  separate worker sends the selected text to the configured provider (Google
  Gemini through the server; off by default, key only in `server/.env`) and
  keeps **only items it can verify**: each fact quotes its document passage
  verbatim with the page; precedent comparisons cite retrieved judgments only;
  invented citations and outcome predictions are removed and counted. Only
  sample (fictional) cases may be analysed until a privacy review allows client
  material. Automated tests and the e2e app use a **scripted test provider**,
  labelled "not AI".
- **Lawyer review and case brief** (Phase 6): every finding starts
  **Unreviewed**; the case's advocates accept, edit (keeping the AI's wording
  visible), reject or clear it, with optional private notes and a full
  history. A **DOCX case brief** contains only accepted findings with their
  citations, and says how many were left out.
- **Outcome assessment** (Phase 7, **synthetic-only demo, off by default**):
  when enabled on a test or e2e database, an assessment of a reviewed run uses
  only the findings and precedent comparisons a lawyer accepted. It lists the
  precedents it relies on with verified quotes and a stance, gives reasoning
  steps that each rest on accepted findings or cited precedents, an
  **uncertainty category (never a number or probability)**, missing evidence
  and limitations. It is produced by a scripted provider (not AI), validated
  strictly, labelled as decision support and as a demonstration on synthetic
  data, and becomes part of the brief only after a lawyer accepts it. See
  [`docs/DEMO_GUIDE.md`](docs/DEMO_GUIDE.md).
- LexFlow's AI is **decision support**; it does not replace a lawyer's
  judgment or a court's decision.
- The top-bar search and notifications are placeholders; "Notifications" in
  the sidebar is marked "Soon".

---

## Getting started (Windows)

Prerequisites: **Node.js 20+** (developed on Node 24), **Python 3.12** and
**Docker Desktop**.

1. **Back end** — follow [`server/README.md`](server/README.md) once: create
   `server/.env` with your own database password, the Python environment, start
   PostgreSQL, apply the migrations and **create the first Administrator**:

   ```powershell
   cd server
   .venv\Scripts\python -m alembic upgrade head
   .venv\Scripts\python -m lexflow.cli.users create --email you@example.com --name "Your Name" --role Administrator
   .venv\Scripts\python -m lexflow.seed     # optional fictional sample data (development only)
   ```

   A database from an earlier phase needs the newer migrations (0002 to 0008):
   **back it up first** (see `server/README.md`). Files uploaded before 0008
   are queued for text extraction only when you ask
   (`python -m lexflow.cli.documents queue-extraction`, preview first).

2. **Every day**, in three terminals:

   ```powershell
   # terminal 1: database and API (http://127.0.0.1:8000, docs at /docs)
   cd server
   docker compose up -d --wait
   .venv\Scripts\python -m lexflow
   ```

   ```powershell
   # terminal 2: the document worker (extracts the text of uploads)
   cd server
   .venv\Scripts\python -m lexflow.worker
   ```

   ```powershell
   # terminal 3: the web app (http://localhost:5173)
   npm install
   npm run dev
   ```

Sign in with the account you created. Vite forwards `/api` to the API, so the
browser sees one origin and no CORS is granted. To point Vite at a different
API address, copy `.env.example` to `.env.local` (ignored by git) and set
`LEXFLOW_API_PROXY_TARGET`.

### Scripts

| Command                     | What it does                                                    |
| --------------------------- | --------------------------------------------------------------- |
| `npm run dev`               | Start the development server                                    |
| `npm run lint`              | ESLint; fails on any warning                                    |
| `npm run format`            | Format the code with Prettier                                   |
| `npm run format:check`      | Check formatting without changing files                         |
| `npm run typecheck`         | TypeScript (app, tests, E2E tests and configs), no output       |
| `npm test`                  | Front-end tests once (Vitest + React Testing Library + MSW)     |
| `npm run test:watch`        | Front-end tests in watch mode                                   |
| `npm run e2e`               | End-to-end tests (Playwright); needs Docker running, see below  |
| `npm run api:types`         | Regenerate `src/services/api/schema.gen.ts` from the API schema |
| `npm run api:check`         | Fail if those types are out of date                             |
| `npm run sample-data:check` | Fail if the seed JSON differs from `src/data/mockData.ts`       |
| `npm run build`             | Type-check and build for production into `dist/`               |
| `npm run preview`           | Serve the production build (also forwards `/api`)               |
| `npm run check`             | Lint, format, typecheck, both drift checks, tests and build     |

Back-end commands (tests, Ruff, mypy, migrations, accounts, purging deleted
documents) are in `server/README.md`.

### Changing the API

The API's OpenAPI document is the contract between the two halves:

1. change the server, then `server\.venv\Scripts\python server\scripts\export_openapi.py`
   (writes `server/openapi.json`);
2. `npm run api:types` (regenerates the TypeScript types the front end uses);
3. fix any type errors. CI fails if either generated file is stale.

---

## Testing

| Suite | Where | What it runs against |
| --- | --- | --- |
| Back end (pytest) | `server/tests/` | the real FastAPI app and a real PostgreSQL test database, rebuilt with the migrations each run |
| Front end (Vitest) | `src/**/*.test.ts(x)` | the real routes, providers and pages in jsdom; the API is faked **at the network boundary** with MSW (`src/test/mockApi.ts`), mirroring the server's rules, shapes, codes and messages |
| End-to-end (Playwright) | `e2e/` | Chromium, the Vite dev server, the real API and a separate `lexflow_e2e` database |

The back-end tests cover, besides the Phase 1 ground (schema and migrations,
validation, uploads and downloads, local-only protections): sign-in, sessions,
CSRF and Origin checks, lockout and the account command line; **every route
refusing anonymous callers** (enumerated from the OpenAPI document); each role's
access to each action and field on a case; editing, archiving and teams;
hearings and the firm-wide schedule; soft deletion, restore and the purge
command; clients; the client portal's **isolation** (every staff route refuses
a Client, every portal route refuses staff, one client never reaches
another's records); account administration; and the audit log, including that
it never holds a password. Security-relevant rules were each checked to fail
their tests when the guarding line was removed (see the Phase 2 execution log).

The front-end tests cover the screens' states and what each role is offered,
with the fake API enforcing the same rules as the server.

### End-to-end tests

```powershell
docker compose -f server/compose.yaml up -d --wait
npx playwright install chromium     # first time only
npm run e2e
```

Global setup drops and recreates the **`lexflow_e2e`** database (same server and
credentials as `DATABASE_URL`), applies the migrations, loads the sample data,
creates the test accounts with a **random password for that run** (kept in the
git-ignored `e2e/.state`, passed through an environment variable, never on a
command line), empties `server/var/e2e-uploads` and starts an API on
`127.0.0.1:8001`. Vite runs on port 5174 and forwards `/api` there. Your
development database and uploads are never touched.

The tests sign in and out, check the lockout and the CSRF header, check what
each role sees and what the server refuses when the screens are bypassed, edit,
archive and restore a case, build a case team, delete and restore a document
(byte-identical), schedule, change and cancel a hearing, add a client and open
their first case, share a document with a client and see it in the portal (and
leave it when unshared), administer an account from creation to disabling, read
the audit log, upload and download files, restart the API and check everything
is still there.

Stopping the API is identity-checked: each start puts a random run id on the
API's command line, and the harness only stops a process whose command line
still carries that id (`e2e/harness.spec.ts` tests this with decoy processes).

### Continuous integration

`.github/workflows/ci.yml` runs on pushes to `master`/`main` and on pull
requests, with three jobs:

- **frontend:** `npm ci`, lint, format check, typecheck, `api:check`,
  `sample-data:check`, tests, build;
- **backend:** PostgreSQL 17 service, Python 3.12, pinned requirements, Ruff
  (lint and format), mypy (strict), `alembic upgrade head`, pytest, OpenAPI
  drift check;
- **e2e:** PostgreSQL service, Playwright Chromium, `npm run e2e`; the report
  and the API's request log (method, path, status; no credentials) are kept as
  an artifact when a test fails.

The repository has no GitHub remote, so the workflow has not run on GitHub. The
same commands have been run locally.

---

## Architecture

```
 Browser ── staff app (/app) and client portal (/portal)
                │                                   │
      hooks (TanStack Query)        useCaseAnalysis / useFindingReviews / useAssessments
                │                                   │
      typed API client (src/services/api)    AI service seam → the LexFlow server only
                │  fetch /api/... (session cookie, X-LexFlow-Request header)
 Vite dev server ── proxy /api ──► FastAPI on 127.0.0.1:8000 (server/lexflow)
                                      │                    │
                              PostgreSQL 17           local disk storage
                           (SQLAlchemy, Alembic)   (server/var/uploads, behind
                                    │                a Storage interface)
                         worker (python -m lexflow.worker): text extraction,
                         optional embeddings, queued AI analyses → Gemini (if set)
```

- **Access control is on the server.** A session gate refuses anonymous
  requests before reading them; routers require the right roles; per-case and
  per-field rules are in `server/lexflow/authz.py`; the portal's queries filter
  on the client's own id. The front end hides what is not allowed, for clarity.
- **Pages talk to hooks, not to `fetch`.** Mutations refresh the affected
  queries; signing in or out clears every cached query.
- **One contract.** The server's Pydantic models produce `server/openapi.json`;
  `openapi-typescript` turns it into `src/services/api/schema.gen.ts`.
- **Errors** are RFC 9457 problem details with a stable `code` and field errors
  in the form's own wording.
- **Nothing is destroyed in the app:** cases are archived, hearings cancelled,
  documents soft-deleted; purging is a separate, guarded command.

### API

| Method & path | Purpose |
| --- | --- |
| `GET /api/health` | API and database status (public) |
| `POST /api/auth/login`, `POST /api/auth/logout` | Sign in and out (public) |
| `GET /api/auth/me`, `POST /api/auth/password` | Who is signed in; change your password |
| `GET /api/cases?archived=`, `POST /api/cases` | Cases you may see; open a case |
| `GET`/`PATCH /api/cases/{id}` | One case with hearings, timeline, documents, team and your permissions; change fields |
| `POST /api/cases/{id}/archive`, `/unarchive` | Archive or restore a case |
| `POST /api/cases/{id}/team`, `DELETE /api/cases/{id}/team/{userId}` | Case team |
| `POST /api/cases/{id}/hearings`, `PATCH /api/hearings/{id}`, `POST /api/hearings/{id}/cancel` | Schedule, change, cancel hearings |
| `GET /api/hearings?from=&to=&includeCancelled=`, `GET /api/hearings/upcoming` | Hearing schedule; upcoming hearings |
| `GET`/`POST /api/cases/{id}/documents`, `GET /api/cases/{id}/documents/deleted` | Documents; upload; deleted ones |
| `GET /api/documents/{id}/download`, `DELETE /api/documents/{id}`, `POST .../restore`, `.../share`, `.../unshare` | Download, (soft) delete, restore, share with the client |
| `GET /api/documents/{id}/text?section=`, `POST /api/documents/{id}/reprocess` | Extracted text, one page or part at a time (audited); extract again |
| `GET /api/cases/{id}/search?q=&mode=keyword\|semantic\|hybrid&limit=` | Passages of the case's documents, best first (audited without the query) |
| `GET /api/judgments`, `/api/judgments/facets`, `/api/judgments/search?q=&mode=&page=` | The judgment collection: browse, filters and available modes, search (staff; searches audited without the query) |
| `GET /api/judgments/{id}`, `/api/judgments/{id}/text?section=` | One judgment with its source and terms; its text page by page |
| `GET /api/cases/{id}/analysis/setup`, `GET`/`POST /api/cases/{id}/analysis-runs`, `GET .../analysis-runs/{runId}` | AI case analysis: what would be sent, start a run, results |
| `GET .../analysis-runs/{runId}/reviews`, `PUT .../reviews/{findingId}`, `GET .../reviews/{findingId}/history`, `GET .../analysis-runs/{runId}/brief` | Lawyer review of findings; the DOCX case brief |
| `GET`/`POST .../analysis-runs/{runId}/assessments`, `GET .../assessments/{id}`, `PUT .../assessments/{id}/review`, `GET .../review/history` | Outcome assessment (Phase 7 demo; 404 unless `LEXFLOW_OUTCOME_ASSESSMENT` is on) |
| `GET`/`POST /api/clients`, `GET`/`PATCH /api/clients/{id}`, `GET /api/clients/options` | Clients |
| `GET /api/advocates`, `GET /api/staff` | Reference lists |
| `/api/portal/cases`, `/api/portal/cases/{id}`, `/api/portal/documents/{id}/download` | Client portal (Client accounts only) |
| `/api/admin/users...`, `GET /api/admin/audit` | Account administration and the audit log (Administrators only) |

Interactive documentation is at http://127.0.0.1:8000/docs while the API runs.

### Project structure

```
src/
├── main.tsx, router.tsx, index.css
├── types/                       # App names for the generated API types; AI contract
├── services/api/                # client.ts (fetch, CSRF header, ApiError), lexflow.ts, schema.gen.ts (generated)
├── services/ai/aiService.ts     # AiService: the server's analysis, review and assessment routes
├── hooks/                       # useCases, useAdmin, useJudgments, useCaseAnalysis, useFindingReviews, useAssessments
├── context/AuthContext.tsx      # Who is signed in (from /api/auth/me); sign-in and sign-out
├── data/mockData.ts             # Fictional sample data (source of the seed JSON)
├── lib/                         # paths, roles, format, fields, caseOptions, documentFiles, ...
├── components/                  # layout/ (app and portal shells), ui/, workspace/, research/, clients/, admin/
├── pages/                       # staff pages, admin/, portal/
└── test/                        # setup, renderApp, mockApi (MSW fake API)
server/
├── lexflow/                     # FastAPI app: api/, services/, auth/, cli/, seed/, extraction/, analysis/, assessment/, worker, authz, audit, models, schemas
├── migrations/                  # Alembic (0001 to 0013)
├── tests/                       # pytest
└── scripts/                     # export_openapi.py, e2e.py, evaluate_*.py (offline SYNTHETIC evaluations)
e2e/                             # Playwright tests and the API start/stop helpers
scripts/                         # api-types.mjs, export-sample-data.mjs
```

---

## Limitations

- **Not reviewed for deployment.** No HTTPS setup, reverse proxy, rate limiting
  beyond the per-account lockout, e-mail (password resets are done by an
  Administrator), or multi-factor sign-in.
- The audit log is append-only through the app and the database but not
  tamper-proof.
- Files are stored unencrypted on the local disk; there is no virus scanning,
  backup or retention policy.
- No OCR. AI analysis checks **provenance, not legal correctness**: a quote
  can be verified while the reading of it is wrong, so every finding needs a
  lawyer's review. The real model's behaviour under the current prompt is
  unverified (owner decision R7).
- **Outcome assessment is a synthetic-only engineering demonstration.** It
  runs only on test or e2e databases, with SYNTHETIC judgments and a scripted
  (non-AI) provider. It never gives probabilities or numeric scores and says
  **nothing about legal accuracy**. Real use is blocked until a judgment source
  is approved, lawyer-labelled evaluation sets with agreed thresholds exist,
  the privacy review is signed off and real-model checks are approved
  (`docs/PHASE7_PLAN.md`, `docs/verification/post-phase6/README.md`).
- **No real judgments** until a source whose terms of use allow it is
  approved and imported. Judgment search quality was measured
  only on synthetic data (`docs/verification/phase4/judgment-eval.md`); real
  legal research quality is **unevaluated** (needs a licensed corpus and a
  lawyer's relevance labels).
- **Embeddings are off by default** and English-only. Semantic search was
  measured only on a small fictional corpus; its quality on real legal
  documents is unmeasured. Case search covers one case at a time and has no
  screen in the app yet.
- Text extraction reads only text layers: scanned PDFs, images and `.doc`
  files have no text. Word headers, footers and comments are not read, and
  Word text has no page numbers (it is shown in parts).

## Status and next steps

Phases 1–6 are implemented and verified (`docs/PHASE*_EXECUTION_LOG.md`,
`docs/verification/`). Phase 7 exists as a synthetic-only demonstration
(`docs/PHASE7_PLAN.md`, `docs/verification/phase7/`). What remains is
external, for the owner: approve a real judgment source, commission
lawyer-labelled evaluation sets and agree thresholds, complete the privacy
review, and decide on real-model checks (`docs/PHASE7_PROPOSAL.md`,
`docs/phase7-prerequisites/`). Requirements, architecture/UML and
traceability: `docs/SRS.md`, `docs/ARCHITECTURE.md`, `docs/TRACEABILITY.md`.
