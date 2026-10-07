# LexFlow — Legal Case Management System

**v0.1 — Initial Working Prototype**

LexFlow is a web application for a legal practice to manage its matters: cases,
clients, hearings, documents, and (later) notifications and role-based access.
This milestone delivers a polished UI and one complete end-to-end flow —
**create a case → see it in the list → open its details** — backed by mock data.

The demo data is set in an **Indian legal context** (Supreme Court of India,
High Courts, District & Sessions Courts; "Advocate" terminology; Indian names,
firms and case references). All people, organisations and matters in the seed
data are entirely fictional and exist only for demonstration.

---

## Tech stack

| Concern            | Choice                        | Why |
| ------------------ | ----------------------------- | --- |
| Language           | **TypeScript**                | Type-safe domain model; catches errors before runtime. |
| UI library         | **React 18**                  | Component model the whole team knows; huge ecosystem. |
| Build tool / dev   | **Vite 5**                    | Instant dev server, near-zero config, fast production builds. |
| Routing            | **React Router 6**            | Standard client-side routing; nested layouts. |
| Styling            | **Tailwind CSS 3**            | Consistent spacing/typography by design tokens; no CSS sprawl. |
| Icons              | **lucide-react**              | Clean, consistent, professional icon set. |
| State (prototype)  | **React Context**             | Enough for mock data; swappable for a real API later. |

No database, no backend, no Docker. `npm install` then `npm run dev` is the
entire setup — appropriate for a college software-engineering project and easy
to demo on any machine.

---

## Project structure

```
Legal Case Management System/
├── index.html                  # Vite entry HTML
├── package.json
├── vite.config.ts
├── tailwind.config.js          # Brand palette (legal navy + muted gold), fonts
├── postcss.config.js
├── tsconfig.json
├── public/
│   └── favicon.svg
└── src/
    ├── main.tsx                # App bootstrap: mounts providers + router
    ├── router.tsx              # Route table (login, app shell, nested pages)
    ├── index.css              # Tailwind layers + shared component classes
    ├── vite-env.d.ts
    │
    ├── types/
    │   └── index.ts           # Domain model: Case, Client, Hearing, User, roles…
    │
    ├── data/
    │   └── mockData.ts        # Seed cases, clients, advocates, demo user (Indian context)
    │
    ├── context/
    │   ├── AuthContext.tsx    # Mock auth (any credentials), localStorage session
    │   └── CasesContext.tsx   # In-memory case store: list / getById / addCase
    │
    ├── lib/
    │   └── format.ts          # Date formatting, initials, case-number generator
    │
    ├── components/
    │   ├── layout/
    │   │   ├── AppLayout.tsx  # Authenticated shell + route guard + <Outlet/>
    │   │   ├── Sidebar.tsx    # Primary nav (future modules shown as "Soon")
    │   │   └── Topbar.tsx     # Search, user menu, sign out
    │   └── ui/
    │       ├── Button.tsx     # Variants: primary / secondary / ghost / danger
    │       ├── Card.tsx       # Card + CardHeader + CardBody
    │       ├── Badge.tsx      # StatusBadge, PriorityBadge
    │       ├── PageHeader.tsx
    │       └── StatCard.tsx   # Dashboard metric tile
    │
    └── pages/
        ├── LoginPage.tsx        # Split-screen branded login
        ├── DashboardPage.tsx    # Metrics, recent cases, upcoming hearings
        ├── CasesPage.tsx        # Searchable + filterable case table
        ├── CaseDetailsPage.tsx  # Summary, timeline, documents, hearings, meta
        ├── NewCasePage.tsx      # "Add New Case" form with validation
        └── NotFoundPage.tsx
```

### How it's kept extensible

- **Domain types are centralised** in `src/types` — pages depend on the model,
  not on the mock data file.
- **Data access is behind hooks** (`useCases`, `useAuth`). Swapping mock data for
  a REST/tRPC API means rewriting two context files; pages are untouched.
- **Sidebar already lists the future modules** (Hearings, Documents, Clients,
  Notifications, Administration) as disabled items, so the information
  architecture is in place.
- **UI primitives** (`components/ui`) give every future screen consistent
  buttons, cards, badges, and spacing.

---

## What's implemented in v0.1

- **Branded login screen** — split layout, product value props, mocked auth
  (any email/password works; pre-filled demo credentials). Session persists via
  `localStorage`; visiting `/app/*` without a session redirects to login.
- **Application shell** — fixed dark navy sidebar, sticky top bar with user menu
  and sign-out, responsive (sidebar collapses to a drawer on mobile).
- **Dashboard** — total / open / in-progress / closed counts, a "Recent Cases"
  list, and an "Upcoming Hearings" panel, all derived from live store data.
- **Cases page** — full-width table with free-text search (title, number,
  client, advocate) and status filter chips; empty state; row click opens the
  case.
- **Case details page** — header with number/status/priority, summary, vertical
  matter timeline, document list, side panel with client / lead advocate /
  court / opposing party / next hearing, and a hearings list. Unknown IDs show a
  friendly "Case not found" state.
- **Add New Case form** — validated fields (title, client, practice area,
  status, priority, lead advocate, opposing party, court, next hearing date,
  summary). On submit it creates the case in the store (auto-assigning a case
  number and an opening timeline entry) and navigates straight to the new
  case's details page.
- **Working flow:** create a case → it appears at the top of the Cases list and
  in the Dashboard → open it to view details.
- **404 page** for unknown routes.

> Everything is in-memory: a full page refresh resets the case list to the seed
> data (the login session is the only thing persisted).

---

## How to run

Prerequisites: **Node.js 18+** (built and tested on Node 24) and npm.

```bash
# from the project root
npm install
npm run dev
```

Vite prints a local URL (default **http://localhost:5173/**) and opens it in
your browser. Sign in with the pre-filled demo credentials (or any email +
password) to enter the app.

Other scripts:

```bash
npm run build      # type-check + production build to dist/
npm run preview    # serve the production build locally
npm run typecheck  # TypeScript only, no emit
```

---

## Recommended Milestone 2

Pick up the modules the architecture is already shaped for, in roughly this
order:

1. **Real persistence + backend.** Add a lightweight API (Express or Fastify +
   Prisma + SQLite — still no infrastructure to run) or a hosted option
   (Supabase). Replace the two context files with API calls; keep the hooks.
2. **Real authentication & role-based access.** JWT or session cookies; enforce
   the `UserRole` model. Gate routes and UI (e.g. Clients see only their own
   matters; Paralegals can't close a case). Turn the current route guard into a
   role-aware one.
3. **Clients module.** List / detail / create-edit, and wire the "Add New Case"
   client field to real client records instead of the mock list.
4. **Hearings module.** Calendar and list views, add/reschedule hearings from
   within a case, and make the Dashboard "Upcoming Hearings" panel actionable.
5. **Documents module.** File upload (local disk or S3-compatible storage),
   per-case document list with download, basic metadata and versioning.
6. **Case editing & status workflow.** Edit an existing case, status
   transitions with audit entries appended to the timeline, and assignment of
   team members.
7. **Notifications.** In-app notification centre (the sidebar item exists) for
   upcoming hearings and case updates; optional email reminders.
8. **Quality baseline.** ESLint + Prettier, a component test setup (Vitest +
   React Testing Library), and one CI workflow running typecheck + tests +
   build.

Nice-to-haves once the above is solid: global search wired to the top bar,
dashboard charts (case load over time), pagination on the cases table, and
CSV/PDF export of a case summary.
