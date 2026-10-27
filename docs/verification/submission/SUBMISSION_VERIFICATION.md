# Submission verification (2026-10-27)

Final check of LexFlow for the Software Engineering project submission,
on commit `bb67d65` (branch `master`). No application code was changed in
this check. The working tree differs from `bb67d65` only in documentation
(see §4). Logs are in `logs/`.

## 1. Automated tests

| Check | Command (repository's own) | Result | Log |
|---|---|---|---|
| Back end | `server\.venv\Scripts\python -m pytest -q` (database `lexflow_test`) | **1246 passed**, exit 0 | `logs/pytest.txt` |
| Lint and format | `ruff check .`, `ruff format --check .` (in `server/`) | all checks passed; 205 files formatted; exit 0 | `logs/static-checks.txt` |
| Types | `mypy` (in `server/`) | no issues in 186 files, exit 0 | `logs/static-checks.txt` |
| API contract | `python scripts/export_openapi.py --check` | `openapi.json` up to date, exit 0 | `logs/static-checks.txt` |
| Front end | `npm run check` (lint, format, typecheck, API types, sample data, Vitest, build) | **212 passed** in 21 files; production build OK; exit 0 | `logs/npm-check.txt` |
| End to end | `npx playwright test` (Chromium, real API, throwaway database `lexflow_e2e_playwright`) | **47 passed**, 0 failed, exit 0 (2.3 min) | `logs/playwright.txt` |

Playwright's global setup rebuilt only `lexflow_e2e_playwright`. It holds the
sample data and 13 SYNTHETIC judgments, and nothing genuine. `e2e.py prepare`
refuses to drop any database that holds genuine judgments.

The earlier mutation checks still apply, because the code has not changed
since they ran:
- Phase 5: 65 of 65 caught (`docs/verification/batch5/logs/phase5-mutation-checks-2.txt`);
- Phase 7: 25 of 25 caught (`docs/verification/batch5/logs/phase7-mutation-checks.txt`).

## 2. Demonstration workflow

**Verified by automated end-to-end tests** (`e2e/`, all passing above):

| Workflow | Spec |
|---|---|
| Sign-in, lockout after five wrong passwords, CSRF header, forced password change | `auth.spec.ts`, `admin.spec.ts` |
| Role-specific access: paralegal, an advocate outside the case, client portal, administrator | `roles.spec.ts`, `portal.spec.ts`, `admin.spec.ts` |
| Create, edit, archive and restore a case; team changes; hearings | `cases.spec.ts`, `case-changes.spec.ts` |
| Upload, open, delete and restore documents (restored file is byte-identical); content and type mismatch refused | `cases.spec.ts`, `case-changes.spec.ts` |
| Background text extraction, page by page; a failed extraction can be retried | `document-text.spec.ts` |
| AI analysis with every claim linked to its source (scripted test provider, not AI) | `analysis.spec.ts` |
| Fictional demo case: file the fictional papers, find the planted contradiction, analyse, lawyer review (accept, edit, reject), export the DOCX brief, synthetic outcome assessment; outsiders refused | `demo-workflow.spec.ts` |
| Judgment search, judgment page with its source, Precedent Library, empty and error states, phone width | `research.spec.ts` |
| Audit log (administrators only) | `admin.spec.ts` |

**Run by hand:** the demo API was started against the persistent demo
database `lexflow_e2e` (`e2e.py serve`, port 8011).
- `/api/health` answered `{"status":"ok","database":"ok"}`.
- Unauthenticated requests to `/api/cases` and `/api/demo/status` answered
  401.
- The process was then stopped.

**Not done:** a manual browser walk-through of `docs/DEMO_GUIDE.md` §5.
Signing in to `lexflow_e2e` first needs the owner's own demo password, set
with `e2e.py accounts`.

## 3. Data safety

**Corpus integrity:** `scripts/verify_corpus_integrity.py verify
var/judgments/sci-tm-v2 --lock ../docs/verification/batch2/corpus-sci-tm-v2.lock.json
--database lexflow_e2e`:
- 17 judgments, 0 problems, database cross-check passed;
- `lexflow_e2e` holds 17 genuine and 13 synthetic judgments, with 30
  provenance rows.

**Live database `lexflow`** (checked in a read-only session):
- migration 0012: 7 cases, 6 clients, 7 users, 32 documents, 3 judgments;
- no provenance table;
- unchanged.

**Never done:**
- no migration;
- no external AI call;
- no Docker volume or database deleted (all three volumes present);
- no commit or push.

## 4. Documentation corrections made in this check

- `README.md`:
  - Playwright uses the throwaway `lexflow_e2e_playwright`, not
    `lexflow_e2e` (two places);
  - the status of the real-model evaluation is updated (synthetic-only run,
    15 of 21 completed; genuine evaluation not approved).
- `docs/SRS.md` §1: outcome assessment is described as the synthetic,
  off-by-default demonstration of FR-20, not as absent.
- `docs/TRACEABILITY.md`: FR-13 and NFR-6 now list the provenance,
  corpus-integrity, prompt-injection and demo-isolation code and tests.

## 5. Submission artifacts

| Artifact | Where |
|---|---|
| Overview, setup (Windows), testing, architecture summary, limitations | `README.md` |
| Requirements (SRS) | `docs/SRS.md` |
| Requirements traceability | `docs/TRACEABILITY.md` |
| Architecture and UML (Mermaid): use cases, deployment, class model, three sequence diagrams, outcome assessment | `docs/ARCHITECTURE.md` |
| Design decisions | `docs/adr/` (21 ADRs) |
| Demonstration guide (setup, accounts, tour, what is synthetic, limitations) | `docs/DEMO_GUIDE.md` |
| Development history and verification | `docs/PHASE*_EXECUTION_LOG.md`, `docs/verification/` |
| Test evidence for this submission | this file and `logs/` |

Not in the repository, so the owner must supply them if the course requires
them:
- screenshots or a recorded demonstration;
- rendered diagram images (the diagrams are Mermaid source, which GitHub
  and many Markdown viewers render);
- any course-specific report template or cover page.

## 6. Limitations (unchanged; see README "Limitations")

- **AI analysis:** demonstrated only with the scripted test provider. The
  synthetic-only real-model run completed 15 of 21 runs.
- **Legal accuracy and research quality:** not evaluated; that needs a
  lawyer's labels.
- **Genuine judgments:** only in the isolated demo database. Licensing for
  wider use is unsettled.
- **Live database:** has not been migrated past 0012.
- **Outcome assessment:** a synthetic, off-by-default demonstration only.
- **Real client material:** requires the D1 privacy review.
- **Deployment:** local only, not production.
