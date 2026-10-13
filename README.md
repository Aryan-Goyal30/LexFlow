# LexFlow — Legal Case Workspace & Research Assistant

**v0.2 — Case workspace prototype, Phase 0 (stabilisation) complete**

LexFlow helps a lawyer work an active case. Each case has its own **workspace**
where the advocate manages the case record and collects the case papers. AI
analysis and precedent research are designed into the workspace but are **not
connected to any AI service yet**.

The intended workflow:

**create or open a case → manage case information → upload documents →
analyse the case → research precedents → review the analysis**

The first three steps work today, in memory. The last three need an AI service
and a collection of past judgments, which are later phases.

The sample data is set in an **Indian legal context** (Supreme Court of India,
High Courts, District & Sessions Courts; "Advocate" terminology). All people,
organisations and matters in it are fictional.

`docs/DEVELOPMENT_BRIEF.md` is the source of truth for the product direction
and the phased roadmap.

---

## What works, what is mocked, what is not built

### Works now

- **Case list** (`/app/cases`, also where `/app` and sign-in land): search by
  title, case number, client or lead advocate; status filters; next hearing
  date (marked when it has passed) and document count per case.
- **New case form:** title (at least 4 characters), client, summary (at least
  10 characters) and lead advocate are required; a next hearing date cannot be
  in the past. Errors are shown next to each field and focus moves to the first
  one. On success the new case opens on its Documents tab.
- **Case workspace** (`/app/cases/:caseId`) with four tabs: Overview,
  Documents, AI Analysis, Research. The selected tab is in the URL
  (`?tab=documents`, `?tab=analysis`, `?tab=research`; no parameter means
  Overview). Each tab change is a browser history entry, so Back and Forward
  move between tabs; re-selecting the current tab adds nothing; an unknown
  `tab` value shows Overview and is removed from the URL. Arrow keys, Home and
  End move between tabs; Enter or Space selects.
- **Documents tab:** add files with the picker or by drag-and-drop. Both follow
  the same rules: PDF, Word (`.doc`, `.docx`), text and images (PNG, JPG, GIF,
  WebP) only; empty files and files whose name is already on the case are
  refused. Each refusal is listed with its reason. Uploaded files can be opened
  in a new tab and removed.
- **AI Analysis tab:** an "Analysis Inputs" panel built from the real case
  record (summary, documents, timeline, parties and forum), a list of what the
  analysis will contain, and a clear "not connected" state.
- **Research tab:** a precedent search box, disabled, with a clear "not
  connected" state.
- **Practice Overview** (`/app/dashboard`): case counts, recent cases and
  upcoming hearings across all cases. Secondary in the navigation.
- **Sign-in screen and route guard:** opening any `/app` page without a session
  goes to sign-in, then back to the page you asked for.
- **404 page** linking back to the case list.

### Mocked

- **Sign-in is simulated, not secure.** Any email and password are accepted and
  nothing is verified. The "session" is the demo user saved in the browser's
  `localStorage`. There are no real accounts, passwords or roles.
- **Sample data.** Six cases, six clients and five advocates come from
  `src/data/mockData.ts`. Their dates are fixed, so some hearing dates are
  already in the past; the UI marks those.

### Lost on refresh

- Everything except the sign-in session: new cases, changes to documents, and
  uploaded files. Cases live in React state only.
- **Uploaded documents are temporary.** A file is held as a browser object URL
  in the current tab. It is never sent anywhere or stored. The URL is released
  when the document is removed, and the browser frees the rest when the page
  closes. A link to a case created before a refresh shows "Case not found".

### Not connected

- **AI Analysis and Research.** The `AiService` interface in
  `src/services/ai/aiService.ts` is the integration point, but its only
  implementation reports "not connected" and rejects every call. The app never
  calls it while disconnected and never shows generated, sample or simulated
  analysis or precedents.
- The results views (facts with their source documents, legal issues,
  precedents with similarities and differences, contradictions) are built and
  covered by tests that use a fake service, but no real service exists yet.
- **Outcome assessment** is part of the data contract but is deliberately not
  displayed. It is a later stage, after retrieval quality has been evaluated.

LexFlow's AI is meant as **decision support** for the lawyer. It does not
replace a lawyer's judgment or a court's decision, and the UI says so wherever
AI output appears or will appear.

---

## Getting started

Prerequisites: **Node.js 20 or newer** (developed and tested on Node 24) and
npm.

```bash
npm install
npm run dev
```

Vite serves the app at **http://localhost:5173/**. Sign in with the pre-filled
demo details (or any email and password; don't use a real password).

### Scripts

| Command                | What it does                                              |
| ---------------------- | --------------------------------------------------------- |
| `npm run dev`          | Start the development server                              |
| `npm run lint`         | ESLint; fails on any warning                              |
| `npm run format`       | Format the code with Prettier                             |
| `npm run format:check` | Check formatting without changing files                   |
| `npm run typecheck`    | TypeScript, no output                                     |
| `npm test`             | Run the test suite once (Vitest + React Testing Library)  |
| `npm run test:watch`   | Run tests in watch mode                                   |
| `npm run build`        | Type-check and build for production into `dist/`         |
| `npm run preview`      | Serve the production build                                |
| `npm run check`        | Lint, format check, typecheck, tests and build, in order  |

Markdown files are excluded from Prettier; they are edited by hand.

### Continuous integration

`.github/workflows/ci.yml` runs on pushes to `master`/`main` and on pull
requests. It installs from the lockfile with `npm ci`, then runs lint, format
check, typecheck, tests and the production build. The repository has no GitHub
remote yet, so the workflow has not run on GitHub.

---

## Testing

Tests live next to the code (`*.test.ts(x)`). They run in jsdom with React
Testing Library and use the real route table, providers and pages. The only
thing faked is the AI service, the one external boundary, and only in
`src/hooks/useAiAssistant.test.tsx`.

What is covered:

- case creation returns the same case it adds; ids and case numbers stay unique;
- invalid case submissions are refused with field-level messages; a valid one
  opens the new case's Documents tab and lists it first;
- the route guard, sign-in redirects and the 404 page;
- the document rules, applied identically to the picker and drag-and-drop, and
  object URLs revoked on removal;
- the "not connected" states of AI Analysis and Research;
- AI errors, an analysis for the wrong case, superseded searches and late
  responses never become results;
- tab state in the URL, Back/Forward, invalid tab values and keyboard movement.

Tests run the routes in `<MemoryRouter>` rather than the data router used by
the app. Under jsdom, the data router's `fetch` requests fail with an
`AbortSignal` mismatch; the routes have no loaders or actions, so the two
routers behave the same for these tests.

---

## Architecture

```
            Pages & workspace tabs  (src/pages, src/components/workspace)
                 │                              │
   useCases() / useAuth()               useAiAssistant(case)
                 │                              │
     Case store (src/context)          AI service seam (src/services/ai)
                 │                              │
       sample data in memory              "not connected"
      → API + database later           → backend AI pipeline later
```

Pages talk to hooks, not to data sources. `CasesContext` provides cases and the
reference data the new-case form needs (clients, advocates), so replacing mock
data with an API means changing the store. Its functions are synchronous today;
an API version will be asynchronous, and pages will gain loading and error
states.

The `AiService` interface:

```ts
interface AiService {
  readonly connected: boolean;
  analyzeCase(legalCase: Case): Promise<CaseAnalysis>;
  searchPrecedents(legalCase: Case, query: string): Promise<Precedent[]>;
}
```

`useAiAssistant` wraps it. It keeps analysis and research state separate, makes
no calls while disconnected, ignores repeat clicks while an analysis runs,
discards responses that arrive after a newer request or after the workspace
closes, and rejects an analysis whose `caseId` doesn't match the case. Model
calls belong on a server, never in the browser.

### Project structure

```
src/
├── main.tsx, router.tsx, index.css
├── types/
│   ├── index.ts                 # Case, Client, Hearing, CaseDocument, User…
│   └── ai.ts                    # AI contract: CaseAnalysis, Precedent, LegalIssue…
├── services/ai/aiService.ts     # AiService interface + "not connected" implementation
├── hooks/useAiAssistant.ts      # Per-case AI state
├── context/
│   ├── AuthContext.tsx          # Simulated sign-in, localStorage session
│   └── CasesContext.tsx         # Cases, documents, clients, advocates
├── data/mockData.ts             # Fictional sample data
├── lib/
│   ├── format.ts                # Dates (local time), file sizes, case numbers
│   ├── documentFiles.ts         # Which files can be attached, and why not
│   ├── validateNewCase.ts       # New case form rules
│   ├── ids.ts                   # Session-unique ids
│   └── paths.ts                 # Home path, safe return path after sign-in
├── components/
│   ├── layout/                  # AppLayout (route guard), Sidebar, Topbar
│   ├── ui/                      # Button, ButtonLink, Card, Badge, Tabs, PageHeader, StatCard
│   └── workspace/               # Overview, Documents, Analysis, Research tabs; PrecedentCard; AiNotices
├── pages/                       # Login, Cases, NewCase, CaseWorkspace, Dashboard (Practice Overview), NotFound
└── test/                        # Test setup and the renderApp helper
```

---

## Limitations

- No backend, database or file storage; see "Lost on refresh".
- Sign-in is simulated; there are no roles or permissions.
- Cases can be created and viewed, not edited or deleted.
- The top-bar search and notifications bell are placeholders and disabled.
- The sidebar's Precedent Library, Hearings, Clients, Notifications and
  Administration items are marked "Soon".
- No AI analysis, precedent search or judgment collection.

## Next phase

According to `docs/DEVELOPMENT_BRIEF.md`, the next step is **Phase 1: backend and
persistence**: an API with a database for cases and file storage for
documents, with `CasesContext` switched to API calls. Phase 1 has not started.
