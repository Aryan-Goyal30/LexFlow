# LexFlow — demo guide

A guided tour for a presentation or an examiner, using **only fictional sample
data and SYNTHETIC judgments**. Nothing here needs a real client, a real judgment
or a paid AI service.

## 1. What LexFlow is

LexFlow is a local legal case management system for a small Indian law
practice. Each case has a **workspace**:
- the case record, team, hearings and timeline;
- documents and their extracted text;
- precedent research;
- an **AI analysis** whose every item is checked against its source;
- a **lawyer review** of that analysis, with a DOCX case brief of the
  accepted findings.

Clients follow their own matters in a separate **client portal**.

**The problem it addresses:** case papers, hearings and research live in
different places. AI tools state things without showing where they come from.
LexFlow keeps the matter in one place, makes every AI statement point to its
source, and makes a lawyer decide before anything is relied on.

## 2. Users and what each may do

| Role | May |
|---|---|
| **Administrator** | Everything, including accounts, the audit log and archiving |
| **Advocate** | Cases they lead or are on: edit, documents, hearings, start an analysis, review findings, generate and review an outcome assessment |
| **Paralegal** | Assigned cases: documents, hearings, court and opposing party; **read** analysis, reviews and assessments (no reviewers' notes) |
| **Client** | The client portal only: own matters, coming hearings, documents an advocate shared |

## 3. Technology and architecture

| Layer | Technology |
|---|---|
| Front end | React 18, TypeScript and Vite; TanStack Query; types generated from the API's OpenAPI document |
| API | FastAPI (Python 3.12) on `127.0.0.1`; SQLAlchemy 2 and Alembic; session cookies, CSRF header and per-case access rules |
| Worker | `python -m lexflow.worker`: text extraction, optional local embeddings, queued AI analyses |
| Database | PostgreSQL 17 with pgvector (Docker) |

Diagrams (use cases, deployment, data model, sequences):
[`docs/ARCHITECTURE.md`](ARCHITECTURE.md). Requirements:
[`docs/SRS.md`](SRS.md). Decisions: [`docs/adr/`](adr/).

## 4. Two ways to run it

**A. Your development environment** (database `lexflow`), as in the
[README](../README.md#getting-started-windows): API, worker and
`npm run dev`, with the account you created. AI analysis is **off** unless the
owner configures Gemini in `server/.env`. The **outcome assessment cannot be
switched on here**: the settings refuse it for this database.

**B. The isolated demo environment (recommended for the full tour).** It
uses a separate database, `lexflow_e2e`, built from the sample data and the
SYNTHETIC judgments, and the **scripted test provider (not AI)**. The
outcome-assessment demo is on. Your development database is never touched.

**Since Batch 2, `lexflow_e2e` also holds 17 genuine Supreme Court judgments**
(`docs/verification/batch2/FINAL_IMPORT_REVIEW_sci-tm-v2.md`). So it is now
**persistent**:
- `prepare` refuses to reset it (it refuses to drop any database that holds
  genuine judgments);
- set the demo password with `accounts` instead;
- Playwright uses its own throwaway database, `lexflow_e2e_playwright`.

```powershell
# Once: Docker Desktop running, server/.env and server/.venv set up (server/README.md)
docker compose -f server/compose.yaml up -d --wait

# Terminal 1 — set the demo password (no reset), then run the API on 127.0.0.1:8001
cd server
$env:LEXFLOW_E2E_PASSWORD = "<choose a demo password, at least 12 characters>"
.venv\Scripts\python scripts\e2e.py accounts
$env:LEXFLOW_EMBEDDINGS = "local"   # meaning-based search with the local model files
.venv\Scripts\python scripts\e2e.py serve

# Terminal 2 — the worker for the demo database (any 32 hex characters as the run id)
cd server
.venv\Scripts\python scripts\e2e.py work --run-id 0123456789abcdef0123456789abcdef

# Terminal 3 — the web app on http://localhost:5174, forwarding /api to the demo API
$env:LEXFLOW_API_PROXY_TARGET = "http://127.0.0.1:8001"
npx vite --port 5174
```

**Sign in** at http://localhost:5174 with the password you chose:

| Account | Role |
|---|---|
| `aryan.goyal@lexflow.test` | lead advocate of the Sattvik case |
| `e2e.paralegal@lexflow.test` | paralegal on that case |
| `e2e.admin@lexflow.test` | Administrator |
| `e2e.client@client.example` | the Sattvik case's client (portal) |

`prepare` builds a fresh demo database. It refuses `lexflow_e2e` while that
database holds the genuine judgments. `npm run e2e` runs the same environment
automatically, in `lexflow_e2e_playwright`, with its own random password.

**Services:** Docker runs only PostgreSQL (`server/compose.yaml`, one `db`
service, `127.0.0.1` only). The demo API, the worker and Vite run on your
computer.

**Settings** (names only; values are yours and never shown):

| Setting | Role in the demo |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD` | Read by `server/compose.yaml` from `server/.env` |
| `DATABASE_URL` | In `server/.env`. The demo uses the same server, with the database name replaced by `lexflow_e2e` |
| `LEXFLOW_E2E_PASSWORD` | Your demo password, for `prepare` or `accounts` |
| `LEXFLOW_E2E_DATABASE` | Optional, default `lexflow_e2e`; the name must contain the part `e2e`. Playwright sets `lexflow_e2e_playwright` |
| `LEXFLOW_EMBEDDINGS` | `local` for semantic and hybrid search, with the pinned model files in `server/var/models` (nothing is downloaded) |
| `LEXFLOW_AI_PROVIDER` | Forced to `scripted` (not AI) by `e2e.py`; the Gemini key is blanked for the demo |
| `LEXFLOW_DEMO_MODE`, `LEXFLOW_OUTCOME_ASSESSMENT` | Set to `true` by `e2e.py` (it uses `setdefault`, so you can switch either off by setting `false`) |
| `LEXFLOW_API_PROXY_TARGET` | Tells Vite where the demo API is |

**What stops the demo from touching the live database:**
- **`prepare` refuses**, before connecting, any target whose name lacks the
  part `e2e`, or that is the `DATABASE_URL` database itself.
- **Identity before writes.** After creating the database, `prepare` marks it
  (`COMMENT ON DATABASE ... 'lexflow:isolated-demo:v1'`). It then asks the
  new connection which database it reached, and checks the marker, before
  migrating or loading anything.
- **The settings refuse** `LEXFLOW_DEMO_MODE`, `LEXFLOW_OUTCOME_ASSESSMENT`
  and the scripted provider unless the database is a test or e2e one.
- **The server re-checks on every request.** A fictional client or case is
  accepted only when the connected database (`current_database()`) is the
  configured one, has a test/e2e name and carries the marker; otherwise it
  answers 409 and writes nothing. The live `lexflow` is never marked.
- **The screen shows the state.** A "Demo environment" banner appears on
  every page when the database is verified, and a red warning when demo
  mode is on but the database is not verified.

**Stopping and cleaning up safely:**
- Stop the three terminals with Ctrl+C. `docker compose -f server/compose.yaml stop`
  stops PostgreSQL and keeps all data.
- **Never use `docker compose down -v`**: it deletes the volume that holds
  every database, the live one included.
- Data you create in the demo lives only in `lexflow_e2e`. The database is
  kept, because it holds the genuine judgments. To remove them, use
  `python -m lexflow.cli.judgments remove --source sci-judgments` against
  it; only then will `prepare` rebuild it.

## 5. The tour

The tour follows a **new, fictional case** built from the tracked document
pack in `server/tests/fixtures/demo-case/`: *Velorindra Foods LLP v.
Tamsinwick Snacks Private Limited (FICTIONAL)*, a trade mark dispute over
KESORA and KESORRA. Its `manifest.json` has the client, the case details,
the timeline and the key facts. `e2e/demo-workflow.spec.ts` runs this same
journey automatically.

1. **Sign in** as the lead advocate. The amber **Demo environment** banner
   is at the top of every page.
2. **Open a fictional client and case.**
   - **Clients → New Client**: tick **Fictional demo client**, then enter
     the manifest's client (name, e-mail, phone).
   - LexFlow then opens **New case** for that client. Tick **Fictional demo
     case**, and enter:
     - the title;
     - practice area *Intellectual Property*;
     - the summary, opposing party and court from the manifest.
   - The case is stored as a sample case, so analysis may run on it (D1 is
     unchanged).
   - A fictional case for a client that is not fictional is refused.
3. **Upload and process the papers.** On **Documents**, attach all six files
   of the pack:
   - 2 PDFs (the plaint, 3 pages; the affidavit, 2 pages);
   - 2 Word files;
   - 2 text files.

   Each one reaches *Text extracted*. Open **View the text** of the plaint
   and move to page 2.
   - **The planted contradiction:** the affidavit (Exhibit P-2, page 1)
     dates invoice VF/INV/0001 to *14 March 2016*; the sales ledger
     (Exhibit P-3) dates it *2 August 2017*.
   - Case search (`GET /api/cases/{id}/search?q=VF/INV/0001`; there is no
     screen yet) finds both, each with its page or part.
   - The scripted provider does not detect contradictions by meaning.
     Whether a real model does is evaluated separately (Milestone 6).

The existing sample case (**Sattvik Foods Pvt. Ltd. v. …**) remains
available for comparison.
4. **Research.**
   - On **Research**, search `prior use trade mark`. Results show the
     passage, page and court.
   - Every judgment is badged **Synthetic test data**.
   - Open one in the **Precedent Library**.
5. **Analyse.**
   - On **AI Analysis**, read "What leaves this computer" and tick the
     confirmation.
   - Click **Analyse case**. The output is labelled *Scripted test output —
     not AI*.
   - Each fact links to its document page, each precedent to its judgment
     passage.
   - The item the scripted provider invented on purpose is shown as
     **removed** by validation.
6. **Review.**
   - Every finding starts **Unreviewed**.
   - **Accept** a fact, **Edit wording** of the precedent comparison (the
     AI's wording stays visible), **Reject** another with a private note.
   - Open **Show history**.
7. **Export the case brief.**
   - **Export case brief (DOCX)** contains only the accepted findings, with
     citations and the decision-support note.
   - The decisions appear on the case timeline (Overview).
8. **Outcome assessment (Phase 7 demo).** Below the analysis, the **Outcome
   assessment (decision support)** card says what it uses.
   - Click **Generate assessment**. It shows:
     - the **Demonstration only** banner;
     - the uncertainty **category** (with the note "a category, not a
       probability");
     - each precedent with its stance, SYNTHETIC badge, verified quote and a
       link to the passage;
     - reasoning steps that name the findings they rest on;
     - missing evidence and limitations;
     - the items the server's checks removed.
   - It is **Unreviewed**: not a lawyer's view and not in the brief.
   - **Accept** it, or **Edit summary**. Export the brief again: it now has
     a separate *Outcome assessment (decision support)* section.
   - Before anything is accepted, the button explains why no assessment can
     be made (the evidence gate).
9. **Roles.**
   - Sign in as the **paralegal**: the analysis, decisions and assessment
     are readable; there are no review controls and no notes.
   - Sign in as the **client**: only the portal.
   - An outsider gets "Case not found".

## 6. What is synthetic, and what is not claimed

- All people, firms and cases are **fictional** sample data.
- **Judgments:** most are **SYNTHETIC** test fixtures, never real case law.
  Since Batch 2, the demo database `lexflow_e2e` also holds **17 genuine
  Supreme Court of India judgments** (trade marks), with these safeguards:
  - each carries a "Genuine judgment" badge, its attribution and its source
    link;
  - the Precedent Library can filter genuine or synthetic;
  - they are for reference only. Search matches text and does not judge
    legal relevance.

  Provenance: `docs/verification/batch2/FINAL_IMPORT_REVIEW_sci-tm-v2.md`.
- **The outcome assessment never uses a genuine judgment.** If an accepted
  precedent comparison is genuine, it answers "insufficient"
  (`genuine-precedents`).
- In the demo environment, analysis and assessment are written by a
  **scripted provider, not AI**. The assessment's stances are assigned by
  position, to show the workflow.
- **No legal accuracy is claimed.** Validation checks provenance and keeps
  forbidden forms out:
  - quotes must exist in their source;
  - every reference must be accepted or retrieved;
  - no probabilities, predictions or invented citations.

  It does not check that a reading is legally right.
- Real use of outcome assessment is **blocked** until a judgment source is
  approved, lawyer-labelled evaluation sets with agreed thresholds exist, the
  privacy review is signed off and real-model checks are approved
  ([`PHASE7_PLAN.md`](PHASE7_PLAN.md)).

## 7. Running the tests

```powershell
cd server; .venv\Scripts\python -m pytest -q           # back end (uses lexflow_test)
cd ..; npm run check                                   # lint, types, contract drift, Vitest, build
npm run e2e                                            # Playwright (uses lexflow_e2e_playwright)
server\.venv\Scripts\python server\scripts\evaluate_assessment.py   # 24 SYNTHETIC assessment scenarios
server\.venv\Scripts\python docs\verification\phase7\run_mutation_checks.py   # 25 guard checks
npx playwright test e2e/demo-workflow.spec.ts           # the new-case demo journey only
cd server; .venv\Scripts\python -m pytest -q tests/test_demo_mode.py tests/test_demo_case.py
```

Recorded results:
- `docs/verification/phase7/README.md`;
- for the demo environment, `docs/verification/engineering-plan/` (its
  `progress-log.md` and the `m1/` logs).

To regenerate the document pack after editing `server/tests/demo_case.py`,
run `server\.venv\Scripts\python server\scripts\make_demo_case.py`.

## 8. Limitations

- Local use only (`127.0.0.1`), not reviewed for deployment.
- No OCR. Embeddings are off by default and English-only.
- The real AI model's behaviour under the current prompt is unverified.
- The outcome assessment is a demonstration, without real judgments or a
  real model.
- Assessment review actions are not added to the matter timeline.
