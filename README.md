# LexFlow — Legal Case Workspace & Research Assistant

**v0.2 — Case workspace prototype, AI-ready architecture**

LexFlow helps a lawyer work an active case from intake to argument. Each case
has its own **workspace** where the advocate manages the case record, collects
the case papers, and — once the AI pipeline is connected — analyses the case and
researches relevant precedents.

The primary workflow:

**create / open a case → manage case information → upload documents →
analyse the case → research precedents → review the analysis**

The demo data is set in an **Indian legal context** (Supreme Court of India,
High Courts, District & Sessions Courts; "Advocate" terminology; Indian names,
firms and case references). All people, organisations and matters in the seed
data are entirely fictional and exist only for demonstration.

---

## Product direction

The long-term goal is an assistant that can read a complete case and its
documents and:

- extract the key facts and the legal issues they raise,
- retrieve relevant precedents from a legal knowledge base,
- compare historical cases with the current one — similarities, differences,
  and contradictions in the record,
- summarise the relevant judgments, and
- eventually offer an evidence-supported outcome assessment.

**LexFlow is decision support, not a substitute for a lawyer or a judge.** Every
AI output is meant to cite its source so the advocate can verify it, and the UI
says so wherever AI output appears.

### What is honest about this build

**No AI is implemented yet.** The workspace, the data contract, and the
integration seam are in place; the model, the retrieval pipeline and the legal
knowledge base are later milestones. The AI Analysis and Research tabs show a
clear "not connected" state — they never display generated or sample output.

---

## Tech stack

| Concern            | Choice                        | Why |
| ------------------ | ----------------------------- | --- |
| Language           | **TypeScript**                | Type-safe domain model and AI contract; catches errors before runtime. |
| UI library         | **React 18**                  | Component model the whole team knows; huge ecosystem. |
| Build tool / dev   | **Vite 5**                    | Instant dev server, near-zero config, fast production builds. |
| Routing            | **React Router 6**            | Client-side routing, nested layouts, tab state in the URL. |
| Styling            | **Tailwind CSS 3**            | Consistent spacing/typography by design tokens; no CSS sprawl. |
| Icons              | **lucide-react**              | Clean, consistent, professional icon set. |
| State (prototype)  | **React Context + hooks**     | Enough for in-memory data; swappable for a real API later. |

No database, no backend, no Docker. `npm install` then `npm run dev` is the
entire setup.

---

## Architecture

```
            Pages & workspace tabs  (src/pages, src/components/workspace)
                 │                              │
        useCases() / useAuth()          useAiAssistant(case)
                 │                              │
     Case store (src/context)          AI service seam (src/services/ai)
                 │                              │
       mock seed data today            "not connected" today
      → REST API + database later      → backend RAG pipeline later
```

Pages never talk to data sources directly — only to hooks. That keeps two
clean seams:

1. **Case data** — `src/context/CasesContext.tsx` holds cases and documents in
   memory. Replacing its internals with API calls changes no page.
2. **AI** — `src/services/ai/aiService.ts` defines the `AiService` interface:

   ```ts
   interface AiService {
     readonly connected: boolean;
     analyzeCase(legalCase: Case): Promise<CaseAnalysis>;
     searchPrecedents(legalCase: Case, query: string): Promise<Precedent[]>;
   }
   ```

   The only implementation today reports that nothing is connected. To
   integrate the pipeline, write an implementation that calls a backend
   (document ingestion → embedding → retrieval over the judgment corpus →
   model synthesis with citations) and export it from that file. The result
   types in `src/types/ai.ts` — facts, issues, precedents with
   similarities/differences, contradictions, optional outcome assessment — are
   already rendered by the Analysis and Research tabs.

Model calls belong on a server, not in the browser: API keys stay private,
documents are processed server-side, and the knowledge base is shared across
the firm.

---

## Project structure

```
src/
├── main.tsx                     # App bootstrap: providers + router
├── router.tsx                   # Routes; /app opens on the case list
├── index.css                    # Tailwind layers + shared form classes
│
├── types/
│   ├── index.ts                 # Domain model: Case, Client, Hearing, Document, User…
│   └── ai.ts                    # AI contract: CaseAnalysis, Precedent, LegalIssue…
│
├── services/ai/
│   └── aiService.ts             # AiService interface + "not connected" implementation
│
├── hooks/
│   └── useAiAssistant.ts        # Per-case AI state (status, results, errors)
│
├── context/
│   ├── AuthContext.tsx          # Mock auth, localStorage session
│   └── CasesContext.tsx         # Cases + documents: add case, upload/remove documents
│
├── data/mockData.ts             # Seed cases, clients, advocates, demo user
├── lib/format.ts                # Dates, file sizes, initials, case numbers
│
├── components/
│   ├── layout/                  # App shell: AppLayout (route guard), Sidebar, Topbar
│   ├── ui/                      # Button, Card, Badge, Tabs, PageHeader, StatCard
│   └── workspace/               # Case workspace tabs
│       ├── OverviewTab.tsx      #   summary, timeline, parties, hearings
│       ├── DocumentsTab.tsx     #   upload (drag & drop), open, remove
│       ├── AnalysisTab.tsx      #   AI analysis: inputs, planned output, results view
│       ├── ResearchTab.tsx      #   precedent search + results view
│       ├── PrecedentCard.tsx    #   one judgment with similarities / differences
│       └── AiNotices.tsx        #   status pill, not-connected state, decision-support note
│
└── pages/
    ├── LoginPage.tsx
    ├── CasesPage.tsx            # Home: searchable case list
    ├── NewCasePage.tsx          # Create a case → lands on its Documents tab
    ├── CaseWorkspacePage.tsx    # The case workspace (tabs: ?tab=documents|analysis|research)
    ├── DashboardPage.tsx        # Secondary practice overview
    └── NotFoundPage.tsx
```

---

## What's implemented in v0.2

- **Case list as the home page** — search (title, number, client, advocate),
  status filters, next hearing and document count per case.
- **New case** — validated form; on submit the case is created and the
  workspace opens on its Documents tab, the next step in the workflow.
- **Case workspace** — one page per case with four tabs; the active tab is in
  the URL, so it can be linked and survives the back button.
  - **Overview** — summary, matter timeline, parties and forum, hearings.
  - **Documents** — drag-and-drop or file-picker upload (PDF, Word, text,
    images), open in a new tab, remove. Files are held as browser object URLs
    for the session.
  - **AI Analysis** — what the analysis will read from this case (a live
    readiness check), what it will produce, and an honest not-connected state.
    The results view for facts, issues, precedents and contradictions is built
    and typed, ready for a real service.
  - **Research** — precedent search UI and results view, disabled with a clear
    explanation until a knowledge base is connected.
- **Overview page** — the earlier dashboard (counts, recent cases, upcoming
  hearings), now secondary in the navigation.
- **Mock sign-in** with a `localStorage` session and a route guard; responsive
  shell; 404 page.

> Everything is in-memory: a full page refresh resets cases to the seed data
> and drops uploaded files. Only the sign-in session persists.

---

## How to run

Prerequisites: **Node.js 18+** and npm.

```bash
npm install
npm run dev
```

Vite opens **http://localhost:5173/**. Sign in with the pre-filled demo
credentials (or any email + password).

```bash
npm run build      # type-check + production build to dist/
npm run preview    # serve the production build locally
npm run typecheck  # TypeScript only, no emit
```

---

## Roadmap

1. **Backend + persistence.** API (e.g. FastAPI or Express) with a database
   for cases and object storage for documents. Replace the internals of
   `CasesContext`; keep the hooks.
2. **Real authentication & roles.** Enforce the `UserRole` model; gate routes
   and actions.
3. **Document ingestion.** Text extraction and OCR for uploaded papers,
   chunking, and embeddings stored per case.
4. **Legal knowledge base.** A corpus of judgments with citation metadata,
   indexed for retrieval.
5. **AI pipeline (RAG).** Implement `AiService` against the backend:
   fact and issue extraction, precedent retrieval and comparison,
   contradiction detection, judgment summaries — every claim linked to its
   source.
6. **Review workflow.** Let the advocate accept, reject or annotate each AI
   finding, with the review recorded on the matter timeline.
7. **Outcome assessment.** Only once retrieval quality is measured; always
   with supporting precedents and the decision-support disclaimer.
8. **Quality baseline.** ESLint + Prettier, Vitest + React Testing Library,
   CI running typecheck, tests and build; an evaluation set for retrieval and
   extraction accuracy.
