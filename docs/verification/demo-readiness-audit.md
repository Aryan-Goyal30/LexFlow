# LexFlow demo-readiness audit (read-only)

- **Date:** 2026-10-25.
- **Repository state:** HEAD `10a44c5` on `master`. Six audit-correction files
  were pending and uncommitted (`CLAUDE.md`, two files in
  `docs/phase7-prerequisites/`, three in `docs/verification/post-phase6/`).
- **Verdict: PARTIAL.** Every step of the workflow works and has been
  exercised. But no single environment can show the full story (create a
  client and a case, upload, analyse, review, export) on one new case, and
  the live database holds material unsuitable for presentation.

**Method:**
- All database queries ran in read-only transactions
  (`default_transaction_read_only=on`) through the project's Docker
  PostgreSQL container.
- Configuration was read from `server/.env` as names and presence only. No
  value of a key, password or token was displayed.
- Document contents were not displayed. Provenance was judged by file
  names, page counts and keyword presence only, and the file name of the
  one non-sample document was withheld.
- No database was written, migrated, reset or seeded. No AI call was made.
  No code, configuration or environment file was changed.

Sections 1–6 are **observed facts**. Section 7 is the **assessment**, and
section 8 the **recommendations**.

## 1. Database inventory (observed)

| Database | Purpose | Alembic revision | Row counts |
|---|---|---|---|
| `lexflow` | Live development database (the target of `DATABASE_URL`: `127.0.0.1:5432/lexflow`, no URL parameters) | `0012` | cases 7, clients 6, users 7, case_members 1, documents 32, document_extractions 5, document_chunks 44, hearings 7, timeline_events 32, judgment_sources 1, judgments 3, judgment_chunks 5, analysis_runs 8, analysis_finding_reviews 10, analysis_finding_review_events 10, audit_events 116, sessions 2 |
| `lexflow_e2e` | Isolated demo and e2e database, rebuilt by `server/scripts/e2e.py prepare` | `0013` | cases 8, clients 7, users 10, case_members 1, documents 35, document_extractions 9, document_chunks 9, hearings 7, timeline_events 37, judgment_sources 1, judgments 13, judgment_chunks 13, analysis_runs 1, analysis_finding_reviews 2, analysis_finding_review_events 2, outcome_assessments 1, outcome_assessment_reviews 1, audit_events 100, sessions 8 (left from that day's Playwright run) |
| `lexflow_test` | Test suite only (`TEST_DATABASE_URL`), recreated by each run | `0013` | every application table 0 |
| `lexflow_pre0012_verify` | Restore check made before migration 0012 | `0011` | cases 7, clients 6, users 7, documents 32, document_chunks 44, judgments 3, analysis_runs 7, audit_events 96, sessions 11 |
| `lexflow_p3_restore` | Older restore check | `0008` | cases 7, clients 6, users 6, documents 28, audit_events 17 |
| `lexflow_restore_check` | Older restore check | `0007` | cases 6, clients 6, users 5, documents 26 |

**Since the pre-0012 snapshot,** the live database gained:
- one analysis run (7 → 8);
- the Phase 6 review tables, with 10 decisions;
- 20 audit events (96 → 116).

## 2. Synthetic versus authentic data in `lexflow` (observed)

| Item | Finding |
|---|---|
| Cases | 6 of 7 flagged sample (fictional). One case is **not** flagged sample: "test" (LF-2026-0490), linked to a sample client. Its one uploaded PDF has no synthetic marker; its content was not displayed, so it is **unclassified** |
| Clients | All 6 flagged sample |
| Users | 1 Administrator and 1 Advocate: real accounts that can sign in. 5 sample advocates without passwords (cannot sign in). **No Client and no Paralegal account** |
| Judgments | **None genuine.** All 3 come from the source `lexflow-demo-synthetic`, "LexFlow SYNTHETIC DEMO judgments — NOT REAL CASE LAW", flagged synthetic. Every judgment's text begins "SYNTHETIC DEMO — NOT REAL CASE LAW…", the court is "SYNTHETIC DEMO COURT (fictional)", the citations are "(SYN-DEMO) 2025 No. 1–3", and the source URLs are on `judgments.lexflow.invalid`. No source URL points to sci.gov.in, eCourts or Indian Kanoon |
| Documents in the Sattvik sample case (LF-2026-0361) | 4 have files and extracted text. One is synthetic (`SYNTHETIC-phase5-smoke-notice.txt`, synthetic marker present). **Three are real, non-legal PDFs**: "Software Testing Using Selenium.pdf" (35 pages), "internship-programs.pdf" (1 page), "Tata Young Social Innovator Challenge- Sector & Problem Statements.pdf" (2 pages). They have no synthetic marker and do not mention the fictional parties |
| Other sample-case documents | 26 are metadata only (no file) |

**In `lexflow_e2e`:**
- all 13 judgments come from the source `lexflow-synthetic`, flagged
  synthetic;
- 6 of its 8 cases are sample cases; the other 2 were created by the e2e
  tests;
- users: 1 Administrator, 3 Advocates who can sign in (plus 3 sample
  advocates who cannot), 2 Paralegals and 1 Client.

## 3. Document processing (observed)

- **No processes running:** no API, worker or Vite process was found, and
  nothing was listening on ports 8000, 8001, 5173 or 5174.
- **`lexflow` documents:**
  - 5 have extraction status `ready`;
  - none is `queued`, `processing` or `failed`;
  - 26 sample documents have no file and no extraction row;
  - one deleted document in the non-sample case has no extraction.

## 4. AI analysis and Gemini (observed)

**Configuration**, from `server/.env`, names and presence only:
- `LEXFLOW_AI_PROVIDER=gemini`, and `GEMINI_MODEL` and `GEMINI_API_KEY`
  are set;
- `LEXFLOW_AI_ALLOW_CLIENT_DATA`, `LEXFLOW_OUTCOME_ASSESSMENT` and
  `LEXFLOW_EMBEDDINGS` are not set, so they default to false, false and
  disabled;
- `LEXFLOW_ENV=development`.

**Persisted analysis runs in `lexflow`:** 8, all on the sample Sattvik case,
provider `gemini`, model `gemini-3.1-flash-lite`.

| Created (UTC) | Status | Documents selected | Judgment passages | Review decisions |
|---|---|---|---|---|
| 10-20 16:29, 16:44, 16:48 | failed (`provider-rejected`) | synthetic notice | 0 | 0 |
| 10-20 16:53 | ready | synthetic notice | 0 | 0 |
| 10-20 17:10 | ready | synthetic notice + the 3 non-legal PDFs | 0 | 0 |
| 10-20 17:47, 17:52 | ready | synthetic notice + the 3 non-legal PDFs | 3 | 0 |
| 10-25 10:19 | ready (4 facts, 3 precedent comparisons) | synthetic notice + the 3 non-legal PDFs | 3 | **10** (9 accepted, 1 rejected) |

**Audit entries:**

| Event | Count |
|---|---|
| `analysis.requested` | 8 |
| `analysis.completed` | 5 |
| `analysis.failed` | 3 |
| `analysis.viewed` | 19 |
| `analysis.finding_reviewed` | 10 |
| `analysis.brief_exported` | 1 |

**`lexflow_e2e`:** 1 ready run by the scripted (non-AI) provider, from the
automated tests.

## 5. Roles and workflow coverage (observed and from the code)

| Step | Live `lexflow` | Isolated demo (`lexflow_e2e`) |
|---|---|---|
| Administrator | Yes | Yes |
| Lawyer (Advocate) | Yes | Yes |
| Client portal | **No Client account exists** (an Administrator could create one; that would be a write) | Yes |
| Create a client and a case | Yes | Yes |
| Upload a document and extract its text | Yes, once the worker runs | Yes, once the e2e worker runs |
| **Analyse a newly created case** | **Refused**: a new case is not a sample case, and decision D1 (`LEXFLOW_AI_ALLOW_CLIENT_DATA=false`) allows only sample cases | **Refused**: `e2e.py` also forces `LEXFLOW_AI_ALLOW_CLIENT_DATA=false` |
| Analyse the sample Sattvik case | Yes, with real Gemini calls (may be billed) | Yes, with the scripted provider (not AI) |
| Review findings and export the brief | Yes (done once already) | Yes (covered by Playwright) |
| Outcome assessment (Phase 7 demo) | Not available, by design: the flag is refused for this database | Yes |

## 6. Reproducibility (observed)

- **The isolated demo is reproducible from the repository**
  (`docs/DEMO_GUIDE.md` §4B: `e2e.py prepare`, `serve` and `work`, Vite on
  port 5174). It needs Docker, `server/.env` with `DATABASE_URL`, and a
  chosen demo password. Its judgment fixtures are tracked in
  `server/tests/fixtures/judgments/synthetic/`. The same setup was rebuilt
  by Playwright earlier on 2026-10-25 (43 passed;
  `docs/verification/phase7/playwright.log`).
- **The live state is not reproducible:**
  - the three demo judgments' manifest is in the git-ignored
    `server/var/demo-judgments/manifest.json` (recorded in
    `docs/PHASE5_EXECUTION_LOG.md`);
  - the uploaded PDFs, the Gemini runs and the review decisions exist only
    in this database.

## 7. Assessment: demonstration gaps

1. **The full flow can't run on one new case.** In both environments, a
   newly created client and case cannot be analysed, because D1 limits
   analysis to sample cases.
2. **There is no synthetic legal document pack.** Only one short synthetic
   notice exists for upload, and 26 sample documents have no files.
3. **Live data is not presentation-ready:**
   - three unrelated real PDFs sit in a fictional case, and the reviewed
     analysis and the exported brief rest partly on them;
   - a non-sample case named "test" holds an unclassified PDF;
   - there is no Client or Paralegal account;
   - analysis on demand makes real Gemini calls.
4. **Nothing is running.** The API, worker and front end must be started
   first, and the isolated demo needs its own worker.
5. **Legal quality is unevaluated.** There are no genuine judgments, and
   real-model behaviour is unverified (register R7 in
   `docs/verification/post-phase6/README.md`).

## 8. Recommendations (not implemented)

1. **Make the isolated demo database the official demo environment.** It
   is reproducible, covers all three roles and the Phase 7 demo, and never
   touches the live `lexflow`.
2. **Prepare a small synthetic legal document pack for upload.** Each
   document clearly labelled SYNTHETIC, consistent with one fictional
   matter.
3. **Allow analysis of newly created cases only in the test/e2e demo
   database.** Use the same safeguard as the outcome-assessment flag:
   settings that refuse it for any other database. D1 stays unchanged for
   the live database.
4. **Keep Gemini an explicit opt-in**, on synthetic documents only, with
   the scripted provider as the default.
5. **For the live database (owner's decision; nothing done):**
   - whether to keep or remove the three unrelated PDFs and the "test" case;
   - whether to create a Client account there.

Items 2 and 3 are the next task. They will be planned and verified
separately.
