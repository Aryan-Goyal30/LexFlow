# LexFlow — Legal Case Workspace & Research Assistant

**v0.4 — Phases 2 and 2b (accounts, roles, case work, client portal) implemented
locally, awaiting review**

LexFlow helps a law firm work its active cases. Each case has its own
**workspace** where the team manages the case record, its hearings and the case
papers. Clients follow their own matters in a separate **client portal**. AI
analysis and precedent research are designed into the workspace but are **not
connected to any AI service**.

The intended workflow:

**create or open a case → manage case information → upload documents →
analyse the case → research precedents → review the analysis**

The first three steps work today and are **saved** in PostgreSQL (files on the
local disk) behind a FastAPI server, with real sign-in and role-based access.
The last three need an AI service and a collection of past judgments, which are
later phases.

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
  see extracted text. Embeddings are **not** computed yet (see Limitations).

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

### Not connected

- **AI Analysis and Research.** The `AiService` interface in
  `src/services/ai/aiService.ts` is the integration point, but its only
  implementation reports "not connected". The app never shows generated, sample
  or simulated analysis or precedents. LexFlow's AI is meant as **decision
  support**; it does not replace a lawyer's judgment or a court's decision.
- The top-bar search and notifications are placeholders; "Precedent Library"
  and "Notifications" in the sidebar are marked "Soon".

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
      hooks (TanStack Query)                 useAiAssistant(case)
                │                                   │
      typed API client (src/services/api)    AI service seam → "not connected"
                │  fetch /api/... (session cookie, X-LexFlow-Request header)
 Vite dev server ── proxy /api ──► FastAPI on 127.0.0.1:8000 (server/lexflow)
                                      │                    │
                              PostgreSQL 17           local disk storage
                           (SQLAlchemy, Alembic)   (server/var/uploads, behind
                                                     a Storage interface)
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
├── services/ai/aiService.ts     # AiService interface + "not connected" implementation
├── hooks/                       # useCases (cases, documents, hearings, clients, portal), useAdmin, useAiAssistant
├── context/AuthContext.tsx      # Who is signed in (from /api/auth/me); sign-in and sign-out
├── data/mockData.ts             # Fictional sample data (source of the seed JSON)
├── lib/                         # paths, roles, format, fields, caseOptions, documentFiles, ...
├── components/                  # layout/ (app and portal shells), ui/, workspace/, clients/, admin/
├── pages/                       # staff pages, admin/, portal/
└── test/                        # setup, renderApp, mockApi (MSW fake API)
server/
├── lexflow/                     # FastAPI app: api/, services/, auth/, cli/, seed/, extraction/, worker, authz, audit, models, schemas
├── migrations/                  # Alembic (0001 to 0008)
├── tests/                       # pytest
└── scripts/                     # export_openapi.py, e2e.py
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
- No AI analysis, OCR, precedent search, judgment collection or outcome
  prediction.
- **No embeddings yet.** Storing vectors needs a PostgreSQL image with
  pgvector; the planned image was not compatible with the existing database
  (different C library), so it was not applied (`docs/adr/0016`). Extracted
  text and chunks are stored and can be embedded later.
- Text extraction reads only text layers: scanned PDFs, images and `.doc`
  files have no text. Word headers, footers and comments are not read, and
  Word text has no page numbers (it is shown in parts).

## Next phase

Phase 3 (document text extraction) is done except embeddings, which wait for
a compatible pgvector database image (`docs/PHASE3_EXECUTION_LOG.md`).
According to `docs/DEVELOPMENT_BRIEF.md`, Phase 4 is the **judgment collection
and retrieval**. It has not started: it needs a judgment source whose terms of
use have been verified, vector storage, and a lawyer's relevance judgments.
`docs/PHASE4_PLAN.md` lists the decisions needed and the proposed milestones.
