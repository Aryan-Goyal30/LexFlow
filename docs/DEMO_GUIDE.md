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
uses a separate database, `lexflow_e2e`, rebuilt from the sample data and the
SYNTHETIC judgments, and the **scripted test provider (not AI)**. The
outcome-assessment demo is on. Your development database is never touched.

```powershell
# Once: Docker Desktop running, server/.env and server/.venv set up (server/README.md)
docker compose -f server/compose.yaml up -d --wait

# Terminal 1 — rebuild the demo database, then run its API on 127.0.0.1:8001
cd server
$env:LEXFLOW_E2E_PASSWORD = "<choose a demo password, at least 12 characters>"
.venv\Scripts\python scripts\e2e.py prepare
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

Running `prepare` again resets the demo. `npm run e2e` runs the same
environment automatically, with its own random password.

## 5. The tour

1. **Sign in** as the lead advocate.
   - Open **Cases** and the **Sattvik Foods Pvt. Ltd. v. …** sample case.
   - Look through the tabs: Overview (hearings, team, timeline), Documents,
     AI Analysis, Research.
2. **Upload and process a document.** On **Documents**, attach a short text
   file, for example a SYNTHETIC notice:

   > SYNTHETIC TEST DOCUMENT. The plaintiff's registered trade mark SATTVIK
   > has been used on packaged snack foods since 2015. The defendant began
   > selling snacks under the mark NISARGA SATTVA in 2024.

   The status changes to *Text extracted*. Open **View text**.
3. **Research.**
   - On **Research**, search `prior use trade mark`. Results show the
     passage, page and court.
   - Every judgment is badged **Synthetic test data**.
   - Open one in the **Precedent Library**.
4. **Analyse.**
   - On **AI Analysis**, read "What leaves this computer" and tick the
     confirmation.
   - Click **Analyse case**. The output is labelled *Scripted test output —
     not AI*.
   - Each fact links to its document page, each precedent to its judgment
     passage.
   - The item the scripted provider invented on purpose is shown as
     **removed** by validation.
5. **Review.**
   - Every finding starts **Unreviewed**.
   - **Accept** a fact, **Edit wording** of the precedent comparison (the
     AI's wording stays visible), **Reject** another with a private note.
   - Open **Show history**.
6. **Export the case brief.**
   - **Export case brief (DOCX)** contains only the accepted findings, with
     citations and the decision-support note.
   - The decisions appear on the case timeline (Overview).
7. **Outcome assessment (Phase 7 demo).** Below the analysis, the **Outcome
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
8. **Roles.**
   - Sign in as the **paralegal**: the analysis, decisions and assessment
     are readable; there are no review controls and no notes.
   - Sign in as the **client**: only the portal.
   - An outsider gets "Case not found".

## 6. What is synthetic, and what is not claimed

- All people, firms and cases are **fictional** sample data.
- All judgments are **SYNTHETIC** test fixtures, never real case law.
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
npm run e2e                                            # Playwright (uses lexflow_e2e)
server\.venv\Scripts\python server\scripts\evaluate_assessment.py   # 24 SYNTHETIC assessment scenarios
server\.venv\Scripts\python docs\verification\phase7\run_mutation_checks.py   # 25 guard checks
```

Recorded results are in `docs/verification/phase7/README.md`.

## 8. Limitations

- Local use only (`127.0.0.1`), not reviewed for deployment.
- No OCR. Embeddings are off by default and English-only.
- The real AI model's behaviour under the current prompt is unverified.
- The outcome assessment is a demonstration, without real judgments or a
  real model.
- Assessment review actions are not added to the matter timeline.
