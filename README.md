# LexFlow — Legal Case Workspace & Research Assistant

**v0.3 — Phase 1 (backend and persistence) implemented, awaiting review**

LexFlow helps a lawyer work an active case. Each case has its own **workspace**
where the advocate manages the case record and collects the case papers. AI
analysis and precedent research are designed into the workspace but are **not
connected to any AI service yet**.

The intended workflow:

**create or open a case → manage case information → upload documents →
analyse the case → research precedents → review the analysis**

The first three steps work today and are **saved**: cases live in PostgreSQL and
uploaded files on the local disk, behind a FastAPI server. The last three need an
AI service and a collection of past judgments, which are later phases.

The sample data is set in an **Indian legal context** (Supreme Court of India,
High Courts, District & Sessions Courts; "Advocate" terminology). All people,
organisations and matters in it are fictional, and the app labels them
**Sample**.

`docs/DEVELOPMENT_BRIEF.md` is the source of truth for the product direction
and the phased roadmap. `docs/PHASE1_EXECUTION_LOG.md` records how Phase 1 was
built and verified, and `docs/adr/` records the main decisions.

> **Local use only.** The API has **no authentication**: anyone who can reach it
> can read and change every case and document. It refuses to listen on anything
> but `127.0.0.1`. Do not expose it to a network or deploy it before Phase 2 adds
> real sign-in. Don't put real client data in it.

---

## What works, what is mocked, what is not built

### Works now (saved in the database)

- **Case list** (`/app/cases`, also where `/app` and sign-in land): search by
  title, case number, client or lead advocate; status filters; next hearing
  date (marked when it has passed) and document count per case. Loading, error
  (with Try again), "no cases yet" and "no matching cases" are distinct states.
- **New case form:** clients and advocates come from the API. Title (at least 4
  characters), client, summary (at least 10 characters) and lead advocate are
  required; a next hearing date cannot be in the past. The browser checks first
  and the server checks again; server errors appear beside their fields and
  nothing typed is lost. The **server allocates the case number**
  (`LF-<year>-<sequence>`, per calendar year in India time). On success the new
  case opens on its Documents tab.
- **Case workspace** (`/app/cases/:caseId`) with four tabs: Overview,
  Documents, AI Analysis, Research. The selected tab is in the URL
  (`?tab=documents`, `?tab=analysis`, `?tab=research`; none means Overview).
  Each tab change is a browser history entry; arrow keys, Home and End move
  between tabs. An unknown case id shows "Case not found".
- **Documents tab:** add files with the picker or by drag-and-drop: PDF, Word
  (`.doc`, `.docx`), text and images (PNG, JPG, GIF, WebP), up to 25 MB each.
  Files are uploaded one at a time with progress text, stored on the server, and
  can be opened in a new tab and removed. The server re-checks every file (type,
  size, empty, duplicate name, and that the **contents match the extension**)
  and its reason is shown when it refuses one. Sample documents are records
  only: "sample record, no file attached".
- **AI Analysis tab:** an "Analysis Inputs" panel built from the saved case
  record, a list of what the analysis will contain, and a clear "not connected"
  state.
- **Research tab:** a precedent search box, disabled, with a clear "not
  connected" state.
- **Practice Overview** (`/app/dashboard`): case counts and recent cases (from
  the case list) and upcoming hearings, all from the API. The hearings panel
  loads and fails independently of the case list.
- **Sign-in screen and route guard** (simulated sign-in; see below) and a
  **404 page**.

### Mocked

- **Sign-in is simulated, not secure.** Any email and password are accepted;
  the "session" is the demo user saved in `localStorage`. The API does not know
  who is signed in. Real accounts and roles are Phase 2.
- **Sample data** is fictional. It is defined in `src/data/mockData.ts`, exported
  to `server/lexflow/seed/sample_data.json`, and loaded into a development
  database by an explicit command. Sample dates are fixed, so some hearing dates
  have passed; the UI marks those.

### Not connected

- **AI Analysis and Research.** The `AiService` interface in
  `src/services/ai/aiService.ts` is the integration point, but its only
  implementation reports "not connected" and rejects every call. The app never
  shows generated, sample or simulated analysis or precedents.
- **Outcome assessment** is part of the data contract but deliberately not
  displayed.

LexFlow's AI is meant as **decision support** for the lawyer. It does not
replace a lawyer's judgment or a court's decision.

---

## Getting started (Windows)

Prerequisites: **Node.js 20+** (developed on Node 24), **Python 3.12** and
**Docker Desktop**.

1. **Back end** — follow [`server/README.md`](server/README.md) once: create
   `server/.env` with your own database password, the Python environment, start
   PostgreSQL and apply the migrations. Then load the fictional sample data
   (development databases only):

   ```powershell
   cd server
   .venv\Scripts\python -m lexflow.seed
   ```

2. **Every day**, in two terminals:

   ```powershell
   # terminal 1: database and API (http://127.0.0.1:8000, docs at /docs)
   cd server
   docker compose up -d --wait
   .venv\Scripts\python -m lexflow
   ```

   ```powershell
   # terminal 2: the web app (http://localhost:5173)
   npm install
   npm run dev
   ```

Sign in with the pre-filled demo details (don't use a real password). Vite
forwards `/api` to the API, so the browser sees one origin and the API needs no
CORS. To point Vite at a different API address, copy `.env.example` to
`.env.local` (ignored by git) and set `LEXFLOW_API_PROXY_TARGET`.

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

Back-end commands (tests, Ruff, mypy, migrations) are in `server/README.md`.

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
| Front end (Vitest) | `src/**/*.test.ts(x)` | the real routes, providers and pages in jsdom; the API is faked **at the network boundary** with MSW (`src/test/mockApi.ts`), mirroring the server's shapes, codes and messages |
| End-to-end (Playwright) | `e2e/` | Chromium, the Vite dev server, the real API and a separate `lexflow_e2e` database |

The back-end tests cover the schema and migrations, sample-data loading (and
refusing to load outside development), validation and RFC 9457 error responses,
case-number allocation under concurrency, the PATCH row lock, uploads (size,
including that an oversized body stops being read at the limit; type, content,
duplicates, storage failures and rollbacks; the work runs off the event loop),
downloads and their headers, and the local-only protections (refusing to listen
beyond 127.0.0.1, Host allow-list, Origin check). Test uploads go to a temporary
folder, never to `server/var/uploads`.

The front-end tests cover the loading and error states of the case list, the
case workspace, the new-case form and Practice Overview; the empty states of
the case list and Practice Overview; an unreachable API (including the dev
proxy's empty 500); keeping data on screen when a refresh fails; client and
server validation errors on the form; uploads with progress and server
rejections, including across tab switches; removing documents, one or several
at once; the route guard; tab state in the URL; and the AI states (with a fake
AI service, the only other faked boundary).

### End-to-end tests

```powershell
docker compose -f server/compose.yaml up -d --wait
npx playwright install chromium     # first time only
npm run e2e
```

Global setup drops and recreates the **`lexflow_e2e`** database (same server and
credentials as `DATABASE_URL`), applies the migrations, loads the sample data,
empties `server/var/e2e-uploads` and starts an API on `127.0.0.1:8001`. Vite runs
on port 5174 and forwards `/api` there. Your development database and uploads
are never touched. The tests sign in, read the case list, create a case and
reload, upload two files, check the downloaded bytes and headers, open a file,
delete one, check that the server rejects a fake PDF, **restart the API** and
check everything is still there, and open an unknown case.

Stopping the API is identity-checked: each start puts a random run id on the
API's command line, and the harness only stops a process whose command line
(as the operating system reports it) still carries that id. A process id left
by an interrupted run, possibly reused by another program, is never signalled.
`e2e/harness.spec.ts` tests this with decoy processes.

### Continuous integration

`.github/workflows/ci.yml` runs on pushes to `master`/`main` and on pull
requests, with three jobs:

- **frontend:** `npm ci`, lint, format check, typecheck, `api:check`,
  `sample-data:check`, tests, build;
- **backend:** PostgreSQL 17 service, Python 3.12, pinned requirements, Ruff
  (lint and format), mypy (strict), `alembic upgrade head`, pytest, OpenAPI
  drift check;
- **e2e:** PostgreSQL service, Playwright Chromium, `npm run e2e`; the report
  and API log are kept as an artifact when a test fails.

The repository has no GitHub remote yet, so the workflow has not run on GitHub.
The same commands have been run locally.

---

## Architecture

```
 Browser ── pages & workspace tabs (src/pages, src/components/workspace)
                │                                   │
      useCases hooks (TanStack Query)        useAiAssistant(case)
                │                                   │
      typed API client (src/services/api)    AI service seam → "not connected"
                │  fetch /api/...
 Vite dev server ── proxy /api ──► FastAPI on 127.0.0.1:8000 (server/lexflow)
                                      │                    │
                              PostgreSQL 17           local disk storage
                           (SQLAlchemy, Alembic)   (server/var/uploads, behind
                                                     a Storage interface)
```

- **Pages talk to hooks, not to `fetch`.** `src/hooks/useCases.ts` wraps each
  endpoint in a TanStack Query query or mutation; mutations refresh the affected
  queries, so the list, the workspace and the dashboard stay in step.
- **One contract.** The server's Pydantic models produce `server/openapi.json`;
  `openapi-typescript` turns it into `src/services/api/schema.gen.ts`, and
  `src/types/index.ts` names those types for the app.
- **Errors** are RFC 9457 problem details (`application/problem+json`) with a
  stable `code` and, for validation, a list of field errors in the form's own
  wording. `ApiError` in `src/services/api/client.ts` carries them to the UI.
- **Files** are stored under random keys, never under the uploaded name. The
  database holds the name, size, type and SHA-256; downloads are streamed with
  `nosniff`, `no-store` and a safe `Content-Disposition`.

### API

| Method & path | Purpose |
| --- | --- |
| `GET /api/health` | API and database status (503 when the database is down) |
| `GET /api/clients`, `GET /api/advocates` | Reference data for the new-case form |
| `GET /api/cases`, `POST /api/cases` | List cases (newest first); create a case |
| `GET /api/cases/{id}`, `PATCH /api/cases/{id}` | One case with hearings, timeline and documents; update fields |
| `GET /api/hearings/upcoming?limit=` | Upcoming hearings across all cases |
| `GET /api/cases/{id}/documents`, `POST /api/cases/{id}/documents` | List; upload one file (multipart, field `file`) |
| `GET /api/documents/{id}/download`, `DELETE /api/documents/{id}` | Download a stored file; delete a document and its file |

Interactive documentation is at http://127.0.0.1:8000/docs while the API runs.
`PATCH` is implemented and tested on the server; the UI has no edit screen yet.

### Project structure

```
src/
├── main.tsx, router.tsx, index.css
├── types/index.ts               # App names for the generated API types (+ mock User)
├── types/ai.ts                  # AI contract: CaseAnalysis, Precedent, LegalIssue…
├── services/api/                # client.ts (fetch, ApiError), lexflow.ts (endpoints), schema.gen.ts (generated)
├── services/ai/aiService.ts     # AiService interface + "not connected" implementation
├── hooks/useCases.ts            # Queries and mutations for cases, documents, reference data
├── hooks/useAiAssistant.ts      # Per-case AI state
├── context/AuthContext.tsx      # Simulated sign-in, localStorage session
├── data/mockData.ts             # Fictional sample data (source of the seed JSON)
├── lib/                         # format, documentFiles, validateNewCase, paths, queryClient
├── components/                  # layout/, ui/ (incl. QueryState), workspace/ (tabs)
├── pages/                       # Login, Cases, NewCase, CaseWorkspace, Dashboard, NotFound
└── test/                        # setup, renderApp, mockApi (MSW fake API)
server/
├── lexflow/                     # FastAPI app: api/, services/, seed/, models, schemas, storage, security
├── migrations/                  # Alembic
├── tests/                       # pytest
└── scripts/                     # export_openapi.py, e2e.py
e2e/                             # Playwright tests and the API start/stop helpers
scripts/                         # api-types.mjs, export-sample-data.mjs
```

---

## Limitations

- **No authentication or authorisation** (Phase 2). The API is protected only
  by listening on `127.0.0.1`, a Host allow-list (against DNS rebinding) and an
  Origin check on writes (against cross-site requests). These protect a local
  development machine; they are not access control.
- Files are stored unencrypted on the local disk; there is no virus scanning,
  backup or retention policy.
- Cases can be created and viewed in the UI, not edited or deleted (the API
  supports `PATCH`).
- The top-bar search and notifications bell are placeholders; several sidebar
  items are marked "Soon".
- No AI analysis, precedent search or judgment collection.

## Next phase

According to `docs/DEVELOPMENT_BRIEF.md`, Phase 2 is **real authentication,
roles and case editing**, on top of this backend.
