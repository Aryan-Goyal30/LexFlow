# Engineering, real-data integration and validation plan — progress log

Append-only record of the owner's ten-milestone plan (received 2026-10-25).
Earlier records are not edited:
- `docs/verification/overnight-completion/`;
- `docs/verification/demo-readiness-audit.md`.

## P0 — Initial inspection (2026-10-25)

### 1. Git

- Branch `master`, HEAD `10a44c5` ("Phase 7 M4: verification and
  documentation"). No remote.
- Working tree: the six pending audit-correction files (`CLAUDE.md`, two in
  `docs/phase7-prerequisites/`, three in `docs/verification/post-phase6/`;
  together +170/−18, the same as when the audit was taken), plus the
  untracked `docs/verification/demo-readiness-audit.md`. **No change since
  the audit.**
- Brief SHA-256 `274ecaed…59b34c2ec`, which matches.

### 2. Docker

- `server/compose.yaml` (project `lexflow`) runs **one** service, `db`:
  `pgvector/pgvector:pg17-trixie`, a named volume `pgdata`, published on
  `127.0.0.1:${LEXFLOW_DB_PORT:-5432}` only, with a `pg_isready` health
  check.
- There is no Dockerfile. The API (`python -m lexflow`), the worker
  (`python -m lexflow.worker`) and Vite run **on the host**.
- All databases (`lexflow`, `lexflow_e2e`, `lexflow_test`,
  `lexflow_pre0012_verify`, `lexflow_p3_restore`, `lexflow_restore_check`,
  and the throwaway `lexflow_migration_test` and `lexflow_eval_test`) live
  in this one PostgreSQL instance and volume. **Isolation is by database
  name only.**

### 3. Database selection and guards (all inspected)

| Path | Target | Guard |
|---|---|---|
| API and worker | `DATABASE_URL` (live: `127.0.0.1:5432/lexflow`) | none needed for ordinary use; test-only settings (scripted provider, outcome assessment) are refused unless the env is test or development **and** a name part is `test`/`e2e`, with no `dbname`/`service` URL parameter (`config.py`) |
| pytest (`tests/conftest.py`) | `TEST_DATABASE_URL` (`lexflow_test`); `DROP`/`CREATE` in `recreate_database` | a name part must be `test`; `dbname`/`service` refused; `TRUNCATE` only in `committed_engine` on that database |
| Migration tests | `lexflow_migration_test` (scratch) | same `_guard` |
| `scripts/e2e.py prepare` | `DATABASE_URL` with its name replaced by `LEXFLOW_E2E_DATABASE` (default `lexflow_e2e`); `DROP ... WITH (FORCE)`, then `CREATE`, `upgrade head`, sample data, accounts, SYNTHETIC judgments | a name part must be `e2e`; `dbname`/`service` refused |
| `scripts/evaluate_judgment_search.py`, `evaluate_retrieval.py` | the hard-coded `lexflow_eval_test` on the `TEST_DATABASE_URL` server | `dbname`/`service` refused |

**Gap:** every guard checks the *name in a URL*. None checks the identity of
the database actually connected to (for example with `current_database()`),
and nothing marks a database as an isolated demo database.

### 4. D1 and Phase 7 gates (code paths)

- **Analysis** is refused for non-sample cases unless
  `LEXFLOW_AI_ALLOW_CLIENT_DATA`. This is checked in:
  - `api/analysis.py` (setup and start);
  - `analysis/runs.py` (`_gate`, the worker's re-check);
  - `api/assessments.py` (list and generate).
- **Outcome assessment:** the `LEXFLOW_OUTCOME_ASSESSMENT` settings guard,
  plus migration 0013 and the router dependency.
- `e2e.py` forces `LEXFLOW_AI_ALLOW_CLIENT_DATA=false`, so **a case created
  in the demo cannot be analysed**: it is not a sample case. This is gap 1
  of the audit.

### 5. The audit's inference, now resolved

The two non-sample cases in `lexflow_e2e` **were created by the e2e tests**
(read-only query):
- "E2E Test Client LLP v. Example Party": `case.created` by "E2E
  Administrator";
- "E2E Test Matter v. Example Party": by "Aryan Goyal".

Both titles are constants in `e2e/case-changes.spec.ts` and
`e2e/cases.spec.ts`, and both events fall inside that Playwright run's
audit window (09:17–09:18 UTC).

### 6. Genuine Indian judgments

Milestone 2 needs the source and licence investigation. The only candidate
assessed so far, `docs/phase7-prerequisites/SOURCE_CANDIDATE_SCI_JUDGMENTS.md`,
is **not approved**:
- the upstream terms were unread (403);
- the licence scope and the licensor are unclear;
- no saved evidence of the pages exists.

### 7. Conflicts between this plan and existing rules

- **Allowing analysis of new cases.** The audit's recommendation 3 would
  relax D1 in the demo database. **Narrower alternative chosen:** do not
  touch D1. Let a user mark a *new* client or case as **fictional** (stored
  as `is_sample=true`, the existing flag that D1 already accepts), **only**
  in a demo database whose identity is verified at request time.
- **Plan items needing approval:** paid model calls (M6, M8) and importing
  genuine judgments (M2) are approval gates; they will be prepared but not
  executed.
- **The plan asks to "work toward all ten milestones"**, but `CLAUDE.md`
  (pending version) says Phase 7 real-world work starts only on the owner's
  instruction. This plan is that instruction for engineering work; the
  external gates (R4–R7) stay gates.

### 8. Proposed first changes (Milestone 1)

1. **`LEXFLOW_DEMO_MODE` setting** (default false), refused unless the env
   is test or development and the database name has a `test`/`e2e` part.
2. **`lexflow/demo.py`: a runtime identity check that fails closed.** A
   demo database counts as verified only if all of these hold:
   - demo mode is on;
   - `current_database()` (the real connection) equals the configured
     name;
   - that name has a `test`/`e2e` part;
   - the database carries the marker comment `lexflow:isolated-demo:v1`
     (`COMMENT ON DATABASE`, a catalog entry written only by
     `e2e.py prepare` when it creates the database).

   No migration is needed. The live `lexflow` has no marker and is never
   written.
3. **Fictional clients and cases.** `POST /api/clients` and
   `POST /api/cases` accept `fictional: true` only when the demo database
   is verified; otherwise they answer 409 and nothing is written. A
   fictional case must use a fictional client. `GET /api/demo` reports the
   status for the UI.
4. **`e2e.py` hardening:**
   - refuse when the target equals the live database name;
   - write the marker after `CREATE DATABASE`;
   - verify `current_database()` before migrating or seeding;
   - turn demo mode on for `serve` and `work`.
5. **A tracked, deterministic, fictional trademark-dispute document pack**
   (PDF, DOCX, TXT) with a manifest naming one deliberate contradiction.
6. **UI:** a "fictional demo" option on the new-client and new-case forms,
   shown only when verified, and a demo-environment banner.
7. **Tests:**
   - backend: verified, unverified and production cases; e2e guards;
   - Vitest;
   - a Playwright journey covering the whole workflow with the pack.

### 9. Safety blockers

None for Milestone 1. Rebuilding `lexflow_e2e` is **necessary** to write
the marker; it is done only by the inspected `e2e.py prepare` (name-part
guard, same server as `DATABASE_URL`). Its current contents are only sample
data, synthetic judgments and e2e-created rows (verified above).

## M1 — Repair the end-to-end demonstration workflow (2026-10-25)

### Changes

**Isolation (1.1):**
- `LEXFLOW_DEMO_MODE` setting (`config.py`), default false. Refused unless
  the env is test or development and the database name has a `test`/`e2e`
  part.
- `lexflow/demo.py`: a runtime identity check that fails closed.
  `status()` is verified only if all of these hold:
  - demo mode is on;
  - `current_database()` on the live connection equals the configured name;
  - that name has a `test`/`e2e` part;
  - the database carries the marker comment `lexflow:isolated-demo:v1`.

  `mark_statement()` refuses any other name.
- `POST /api/clients` and `POST /api/cases` take an optional
  `fictional: true`:
  - accepted only when the demo database is verified (otherwise 409
    `demo-environment-unverified`, nothing written);
  - enforced in both the API and the service;
  - a fictional case needs a fictional client (otherwise 422 on
    `clientId`);
  - fictional records are stored with `is_sample=true`, so **D1 is
    unchanged**;
  - audit details record `fictional: true`.
- `GET /api/demo` (staff only) reports the status.
- **`scripts/e2e.py`:**
  - refuses a target equal to the `DATABASE_URL` database;
  - marks the new database right after `CREATE DATABASE`;
  - `verify_identity()` (`current_database()` plus the marker) runs before
    any migration or seeding;
  - `serve` and `work` turn demo mode on by default (`setdefault`).

**Fictional case and documents (1.2, 1.3):**
- `server/tests/demo_case.py` builds *Velorindra Foods LLP v. Tamsinwick
  Snacks Private Limited (FICTIONAL)*.
- `scripts/make_demo_case.py` writes the tracked pack to
  `server/tests/fixtures/demo-case/`:
  - a plaint (PDF, 3 pages) and an affidavit (PDF, 2 pages);
  - a sales ledger and a cease-and-desist notice (TXT);
  - a reply and a written statement (DOCX);
  - `manifest.json` and a README.
- **Planted contradiction:** invoice VF/INV/0001 is dated 14 March 2016 in
  the affidavit (page 1) and 2 August 2017 in the ledger.
- **Two findings while building the pack:**
  - The built-in PDF font maps `'` to a typographic quote on extraction, so
    PDF text is kept ASCII without apostrophes. (LexFlow's quote validator
    normalises such quotes; exact-text tests do not.)
  - With an identical notice at the **head** of every document, the scripted
    provider's quotes were identical, and validation correctly removed its
    contradiction as "fewer than two distinct verified sources". The notice
    is now at the **foot** of every page and file, and each document opens
    with its own title marked FICTIONAL.

**UI:**
- `DemoBanner`: an `aside` "Demo environment" when verified, a red alert
  when demo mode is on but unverified.
- "Fictional demo client" and "Fictional demo case" options, shown only
  when verified.
- The mock API mirrors the server rules.

**Docs:** `docs/DEMO_GUIDE.md` §4–5:
- services and settings (names only);
- the safety checks;
- safe stop and cleanup (`stop`, never `down -v`);
- the new-case tour;
- test commands.

### Tests added

| File | Tests | Covers |
|---|---|---|
| `test_demo_mode.py` | 11 | settings refusal; marker present, absent, wrong database; 409 and 422; D1 setup `canRun` for a fictional case; e2e guards before connecting; unmarked identity refused |
| `test_demo_case.py` | 21 | the builder matches; every file labelled; real extraction; key facts on the stated page only; contradiction location |
| `src/pages/demo.test.tsx` | 4 | the banner, and fictional records only when verified |
| `e2e/demo-workflow.spec.ts` | 4 | the full new-case journey, steps 1–15, plus access refusals |

`test_openapi.py`'s contract snapshot gained `fictional`, an intended
change.

### Results (final tree; logs in `m1/`)

| Check | Result | Exit |
|---|---|---|
| `pytest -q` | 1138 passed | 0 |
| ruff check and format, mypy, mypy linux, OpenAPI | clean | 0 |
| `npm run check` | 20 files, 205 tests, build OK | 0 |
| `npx playwright test` | 47 passed | 0 |

**Failures fixed on the way:**
- an existing research e2e test hit two `note` roles once the banner
  existed; fixed by making the banner an `aside`;
- the "View text" selector in my spec;
- the pack issues above.

### Database identity checks (read-only)

- **Live `lexflow` after all runs:** revision 0012; cases 7, clients 6,
  users 7, documents 32, runs 8, reviews 10, audit 116, sessions 2,
  judgments 3. **Identical to the audit.**
- **Database comments:** only `lexflow_e2e` carries the marker. The test
  suite's marker was written inside a rolled-back transaction and did not
  persist.

### Steps 16–18 of the plan

- **16. Unsupported predictions, invented citations, numeric
  probabilities:** covered by the existing validation suites (Phase 5 and
  Phase 7, with mutation checks). The journey asserts no percentage in the
  assessment.
- **17. A production database cannot enable demo mode** (settings), and an
  unmarked database is not verified (runtime).
- **18. A destructive setup aimed at the live database fails closed before
  any connection:** `test_the_demo_setup_refuses_the_live_database_before_connecting`
  and `test_the_demo_setup_refuses_an_unmarked_database`.

### Limits

- The scripted provider does not detect the contradiction by meaning; real
  detection is Milestone 6.
- Case search has no screen; the journey uses the API.
- No manual browser walkthrough was done (Playwright drives a real
  browser).
- The live database's unrelated PDFs and its "test" case were left as they
  are, per the plan.

### Preserved

- The six audit-correction files: still +170/−18.
- `demo-readiness-audit.md`: SHA-256 `9be46777…`, unchanged.
- The brief's hash: unchanged.
- No commit, no push.

### Status

**Milestone 1: complete.** The next task is Milestone 2.1: a source and
licence investigation for genuine Indian judgments, documented before any
import. Importing waits for approval (R4).

---

## Batch 2 (Milestones 2–4): safe work done; the import awaits approval (2026-10-25)

### Source and licensing

`docs/verification/batch2/SOURCE_AND_LICENSING_REPORT.md`, with the raw
pages saved in `source-evidence/` (`evidence-manifest.json`, SHA-256 per
file).

- **Recommendation, Option A:** 20–40 English Supreme Court judgments,
  downloaded by hand from e-SCR. They are imported first into the
  evaluation or demo database, never the live one.
- **Finding:** the AWS Supreme Court dataset was collected by a scraper
  that solves the portal's CAPTCHA automatically (`sci-download.py`,
  lines 494–600). Using it (Option B) is the owner's decision.
- India Code timed out, so section 52 is from secondary sources only.

**Nothing has been downloaded or imported.**

### Built, on invented data only

The formats and how to use them are in
`docs/verification/batch2/INGESTION_AND_EVALUATION.md`.

**Ingestion:**
- manifest format 2 (licence, attribution, dataset, neutral citation,
  provenance map);
- migration 0014, which adds two tables: `judgment_provenance` and
  `judgment_import_runs`;
- each run is recorded with every item that was not imported, and why;
- the offline CSV-plus-PDF adapter `scripts/prepare_official_judgments.py`,
  with the `sci-escr` profile and an official-host allowlist.

**Retrieval:**
- an `origin` filter (genuine or synthetic) on list and search;
- provenance in the judgment detail;
- "Genuine judgment" and "Synthetic test data" badges;
- a reliance caution on genuine judgments;
- an origin filter in the UI, shown only when the collection holds both
  kinds.

**Evaluation:**
- nDCG@k, the unjudged-in-top-k count and Cohen's kappa;
- `lexflow/relevance_sets.py`: the lawyer, synthetic and citation-proxy
  set format, scoring with a mandatory label wording, reviewer agreement,
  the candidate pool and a citation-proxy builder.

No labels exist, and none were generated.

**New tests:**
- `test_judgment_provenance.py` (8);
- `test_judgment_selection.py` (12);
- `test_relevance_sets.py` (14);
- 3 in `test_judgments_api.py`;
- `src/pages/provenance.test.tsx` (3).

Contract changes:
- the `origin` query parameter;
- `JudgmentDetailOut.provenance`.

`openapi.json` and `schema.gen.ts` were regenerated.

### Verification (this run; logs in `docs/verification/batch2/logs/`)

| Command | Result |
|---|---|
| `pytest -q` | 1175 passed, exit 0 |
| `ruff check`, `ruff format --check`, `mypy`, `export_openapi --check` | all clean, exit 0 |
| `npm run check`, first run (`npm-check.txt`) | 2 of 208 timed out at 5 s (`demo.test`, `documentText.test`). It ran at the same time as pytest |
| Those 2 files alone (`vitest-rerun.txt`) | 11 passed |
| `npm run check`, alone (`npm-check-rerun.txt`) | 208 passed, build OK, exit 0 |
| `npx playwright test` | 47 passed, exit 0 |

**Live `lexflow`** (read-only, after all runs):
- revision 0012;
- 7 | 6 | 7 | 32 | 8 | 10 | 116 | 2 | 3;
- no `judgment_provenance` table.

**Unchanged.**

`lexflow_e2e`: at 0014, and it carries the marker.

### Preserved

- The six audit-correction files: +170/−18.
- `demo-readiness-audit.md`: `9be46777…`.
- The brief: `274ecaed…`.
- HEAD: `10a44c5`.
- No commit, no push.

### Status

**Batch 2: waiting for the owner's approval** of the source and the import
(Option A into an evaluation database). After approval:
1. import;
2. run graded sets against the search modes;
3. report the first measurement.

---

## Batch 2: automated acquisition of the candidate corpus (2026-10-25)

**Owner instruction:** acquire the corpus automatically wherever permitted;
**do not import**.

**Access findings** (evidence in `docs/verification/batch2/acquisition-evidence/`):
- e-SCR search, and the sci.gov.in search by date, case number and neutral
  citation, are CAPTCHA-protected. **Not used.**
- The Court's own PDF links on `api.sci.gov.in` need no CAPTCHA.
- `www.sci.gov.in/robots.txt` disallows only `/wp-admin/`.
- The Landmark Judgment Summaries list (2017–2026, 125 rows) has no trade
  mark judgment.

**Acquisition:**
- 40 candidate files fetched, one at a time, at least 3 seconds apart, from
  addresses that web search found on the official host. No CAPTCHA solved,
  and no address guessed.
- Classified from their own text: **14 on topic** (10 core, 4 related),
  3 peripheral, 23 off topic.
- **The 17 retained** (14 plus 3 peripheral) were re-fetched: **byte-identical**.
- 6 legacy-archive files carry a verified 4-byte length prefix. It is
  removed in the import copy; the original is kept, and both hashes are in
  provenance.
- **Corpus:** `server/var/judgments/sci-tm-v1/`, Git-ignored.

**Code:**
- `judgment_selection.py`:
  - `sci-judgments` profile;
  - retrieval columns (`retrieved_from`, `retrieved_at`, `original_sha256`,
    `original_transform`, the last required when the file differs);
  - unknown provenance values are left out of the manifest.
- New `scripts/preview_judgment_import.py`: named test or e2e database
  only, identity and marker checked, READ ONLY transaction rolled back.
- New tests: 6 in `test_judgment_selection.py`; `test_import_preview.py` (5).

**Documents:**
- `CORPUS_sci-tm-v1.md`: inventory, method, caveats, not obtained, approval;
- `import-preview-sci-tm-v1.md`;
- `SOURCE_AND_LICENSING_REPORT.md` section 7 (addendum);
- `INGESTION_AND_EVALUATION.md` (profile, columns, preview).

**Corrections during drafting:** 4 figures in the corpus document were
recounted from the data before it was finished:
- characters: 888,450;
- headnotes: 4 of 6;
- neutral citations: 3;
- no citation: 8.

**Dry run** (`lexflow_e2e`, read-only):
- 14 new, 0 changed, 0 duplicate, 0 invalid;
- every file extracted, with no empty pages;
- 8 notes, all "no citation printed".

**Verification (this run):**

| Command | Result |
|---|---|
| `pytest -q` | 1186 passed, exit 0 (`logs/pytest-acquisition.txt`) |
| ruff, format, mypy, OpenAPI check | exit 0 (`logs/static-checks-acquisition.txt`) |
| `npm run check`, Playwright | not rerun; no front-end code or API contract changed since the earlier run |

**Databases (read-only checks):**
- `lexflow_e2e`: no `sci-judgments` source; 13 synthetic judgments and 1
  import run, from the e2e setup.
- Live `lexflow`: 0012 | 7 | 6 | 7 | 32 | 8 | 10 | 116 | 2 | 3.
  **Unchanged.**

**Preserved:**
- the six audit-correction files;
- the audit report;
- the brief hash.

No commit, no push.

### Status

**Waiting for the owner's approval** of the 14-judgment import into
`lexflow_e2e`, and of the open decisions in `CORPUS_sci-tm-v1.md` section 8.

---

## Batch 2: final checks before the import (2026-10-25)

**Owner instruction:** prepare the final preview for the 14-judgment corpus;
**do not import**.

**Headnotes:**
- Of the 4 legacy files with a `HEADNOTE:` label, only *Amritdhara* (2,940
  characters) and *Parle* (2,255 characters) contain headnote text, on
  pages 1–2 before `JUDGMENT:`.
- *Whirlpool* and *Gujarat Bottling* have empty labels.
- Authorship is not stated in the files. Nothing was altered.
- Options per document are in `FINAL_IMPORT_REVIEW_sci-tm-v2.md` section 2.

**Terms:**
- Re-fetched live: the sci.gov.in copyright policy and terms, and e-SCR's
  copyright policy, are identical to the saved evidence.
- Verified permissions and unresolved questions are kept separate (section 3).
- Found: with a real provider, case analysis would place judgment passages
  in prompts. This is not enabled for `lexflow_e2e`.

**Corpus `sci-tm-v2`** (`v1` kept):
- 14 core and 3 evaluation candidates;
- role, "Prepared by" (technical, not a legal review) and "Legal review: not
  performed" recorded per judgment;
- terms record "Technical check only … No legal review yet";
- manifest SHA-256 `4b3134b7…cb3f3`.

**Code:**
- `judgment_selection.py`: `corpus_role`, `legal_review` and `notes` columns.
- Judgment page shows preparation, legal review, role, notes and file change.
- `preview_judgment_import.py`: per-document details.
- New `scripts/import_judgments_isolated.py`. It checks, in order:
  1. the approved manifest hash;
  2. an e2e name that is not `DATABASE_URL`, with no URL parameters;
  3. `current_database()` and the marker.

  Only then does it run the CLI, with `--confirm`.
- Tests: `test_import_preview.py` 11; selection 19; UI provenance test
  extended.

**Preview** (`lexflow_e2e`, read-only, rolled back):
- 17 new, 0 duplicate, 0 invalid;
- every file extracted, with no empty pages;
- 10 notes (8 "no citation printed").

**Isolation** (read-only):
- `DATABASE_URL` names `lexflow`, with no URL parameters.
- Only `lexflow_e2e` carries the marker; it is at 0014, with the synthetic
  source only.
- Container bound to `127.0.0.1` only.
- **Found:** Playwright's global setup drops and recreates `lexflow_e2e`.
  So Playwright was **not run**. After the import it must use a different
  `LEXFLOW_E2E_DATABASE`, or the import must be repeated.

**Verification:**

| Command | Result |
|---|---|
| `pytest -q` | 1193 passed, exit 0 |
| ruff, format, mypy, OpenAPI check | exit 0 |
| `npm run check` | 208 passed, build OK, exit 0 |
| Playwright | not run (it would reset `lexflow_e2e`) |

**After the checks:**
- `lexflow_e2e`: unchanged (synthetic source only, 13 judgments).
- Live `lexflow`: 0012 | 7 | 6 | 7 | 32 | 8 | 10 | 116 | 2 | 3.
  **Unchanged.**

**Preserved:**
- the six audit-correction files (+170/−18);
- the audit report;
- the brief hash;
- HEAD at `10a44c5`.

No commit, no push.

### Status

**Waiting for the owner's approval** of the exact preview
`import-preview-sci-tm-v2.md`, manifest SHA-256
`4b3134b7b9de3d0740153c93463ef9cb7e4fae32b30a9eb8d9b24e48ac4cb3f3`.

---

## Batch 2: import, retrieval and first evaluation; Batch 2 complete (2026-10-25)

**Owner decision:** import the full 17-document preview (manifest
`4b3134b7…cb3f3`).

**Import:**
1. The manifest hash and all 17 import copies and 17 originals were
   re-checked against the reviewed preview: identical.
2. `scripts/import_judgments_isolated.py` passed its checks (approved hash;
   an e2e name that is not `DATABASE_URL`; `current_database()` and the
   marker). The CLI preview showed 17 new.
3. The import with `--confirm 17` gave "Imported 17, updated 0, rejected 0"
   (`logs/import-run.txt`).

**Verification** (new `scripts/verify_judgment_import.py`, read-only):
- every field, content hash, section count, chunk count and provenance
  record matches the manifest;
- the import run shows 17 imported and 0 rejected;
- 17 `judgment.imported` audit events;
- `sci-judgments`: 17 judgments, 631 sections, 1,267 chunks.

**Playwright isolation:**
- Playwright now uses `lexflow_e2e_playwright` (`E2E_DATABASE` in
  `e2e/support/backend.ts`).
- `e2e.py prepare` refuses to drop any database holding genuine judgments
  (`holds_genuine_judgments`, tested).
- New `e2e.py accounts` sets the demo password without a reset (tested).
- Two Playwright runs (47 passed each) left the corpus intact: re-verified
  after each.
- `DEMO_GUIDE.md` updated.

**Retrieval:**
- Local embeddings for 30 judgments (1,280 chunks), via
  `scripts/index_judgments_isolated.py` (`LEXFLOW_EMBEDDINGS=local`, pinned
  files, no download).
- **Keyword fallback:** when no passage has every word, keyword mode ranks
  passages with any word, and reports `keywordMatch: "any"`. The UI says so.
- Hybrid keeps every-word matches. This was decided by measurement: the
  fallback inside hybrid lowered MRR from 0.971 to 0.683.
- API, OpenAPI, types and mock updated; tests added (API 2, UI 2).

**Evaluation** (`EVALUATION_REPORT.md`; runner
`scripts/evaluate_genuine_retrieval.py`):
- **Known-item set** (17 queries, MODEL-GENERATED labels; adopted design):
  - semantic and hybrid: MRR@10 0.971, recall@5 1.000;
  - keyword: MRR@10 0.485 (0.176 before the fallback).
- **Citation-context proxy** (7 queries, NOT lawyer relevance):
  - semantic and hybrid: MRR@10 0.505, recall@5 1.000;
  - keyword: MRR@10 0.191.
- **Limitations are recorded:** optimistic model-written queries, tiny sets,
  no lawyer labels.
- The set format gained `label_origin: model-generated`, which requires its
  author and carries its own report wording (tested).

**Verification (this run):**

| Command | Result |
|---|---|
| `pytest -q` | 1200 passed, exit 0 |
| ruff, format, mypy, OpenAPI check | exit 0 |
| `npm run check` | 210 passed, build OK, exit 0 |
| `npx playwright test` (on `lexflow_e2e_playwright`) | 47 passed, exit 0 |

**Live `lexflow`:** 0012 | 7 | 6 | 7 | 32 | 8 | 10 | 116 | 2 | 3.
**Unchanged.**

**Preserved:**
- the six audit-correction files (+170/−18);
- the audit report;
- the brief hash;
- HEAD `10a44c5`.

No commit, no push.

### Status

**Batch 2: complete.** Next: Batch 3 (Milestones 5 and 6).

---

## Batch 3: Milestones 5 and 6, deterministic work complete (2026-10-26)

Full report: `docs/verification/batch3/BATCH3_REPORT.md`.

**Milestone 5, document intelligence:**
- **New `scripts/validate_document_intelligence.py`** (read-only, on the 17
  genuine judgments):
  - fresh re-extraction equals the stored text (631 pages);
  - every one of the 1,267 chunks is an exact slice of its page, with no
    gaps;
  - all hashes match.
- **Finding:** references are PDF pages. *Lifestyle Equities* prints page
  N − 1, because of an unnumbered cover page; this is reported as a
  warning. A fix (a printed page label per page) is proposed, not built.
- **Defect fixed:** identical content under another name was accepted on
  one case, so analysis counted it twice. It is now refused on upload and
  restore (409 `duplicate-content`); 3 tests added.
- **Limits recorded:**
  - no OCR (scans fail with a visible reason);
  - text completeness is checked for consistency only (one PDF library).
- An evidence matrix maps every Milestone 5 item to named tests.

**Milestone 6, AI case analysis:**
- `evaluate_analysis.py`: 0 mismatches
  (`phase5/analysis-eval-batch3-2026-10-26`).
- **Defect fixed (validator `grounding-5`):** text in a document that reads
  like instructions to an AI system is never evidence.
  - Under `grounding-4`, a compromised model could keep a false fact, an
    invented citation (in a fact or a precedent) and a fake contradiction,
    all drawn from injected text.
  - Now quotes from that text are removed (`instruction-text`), it cannot
    vouch for a citation, and the result lists the passages
    (`instructionLikePassages`, with an amber warning in the UI).
  - False positives: 0 on 1,267 genuine chunks and on 6 ordinary
    legal-prose cases.
  - Tests: `test_prompt_injection.py` (21) and 2 UI tests.
- **Real-model evaluation:** `REAL_MODEL_APPROVAL_REQUEST.md`.
  - 21 runs, at most 63 calls to `gemini-3.1-flash-lite`;
  - estimated USD 0.15 to 1.80 at the recorded prices;
  - fictional, synthetic and (optionally) public judgment data.
  - **Pending the owner's approval. No call was made.**

**Test isolation:**
- A pre-existing order-dependent failure (`test_documents.py`, then
  `test_portal.py`) reproduced at HEAD `10a44c5` in a temporary worktree,
  since removed. The test now counts only its own audit events.
- The `make_ready` fixture now gives each document its own hash.

**Verification (final):**

| Command | Result |
|---|---|
| `pytest -q` | 1224 passed, exit 0 |
| ruff, format, mypy, OpenAPI check | exit 0 |
| `npm run check` | 212 passed, build OK |
| Playwright (`lexflow_e2e_playwright`) | 47 passed |

The two earlier pytest runs, with 1 failure each, are recorded in the
report with their causes.

**Corpus:** `lexflow_e2e`, re-verified.

**Live `lexflow`:** 0012 | 7 | 6 | 7 | 32 | 8 | 10 | 116 | 2 | 3.
**Unchanged.**

**Preserved:**
- the six audit-correction files;
- the audit report;
- the brief hash;
- HEAD `10a44c5`.

No commit, no push.

### Status

**Batch 3:** the deterministic work is complete; the real-model evaluation
waits for approval.

**Next:** Batch 4 (Milestone 7, security and privacy review; Milestone 8,
real-model evaluation after approval).

---

## Batch 4: Milestones 7 and 8, focused, under a token budget (2026-10-26)

Report: `docs/verification/batch4/BATCH4_REPORT.md`.

**Milestone 7 (focused review):**
- **No new high-impact defect.** The evidence matrix covers access, roles,
  sessions, uploads, audit, isolation, secrets and AI data flow.
- **Residual risks recorded:**
  - judgment text sent to a real provider;
  - the development cookie is not Secure;
  - the audit table's owner can bypass the trigger;
  - injection detection is pattern-based;
  - a document can state falsehoods as ordinary prose.

**Printed page labels:** documented as a known limitation (it needs a
migration, re-extraction and UI changes).

**Milestone 8:**
- Gemini terms re-verified (2026-04-28 version).
- **Harness:** `scripts/evaluate_analysis_real.py`. It plans by default,
  with no call; execution requires the plan's SHA-256 and Gemini.
  Tests: `test_real_model_harness.py` (4).
- **Plan:** `9bbdb013…f207`, estimated USD 0.11 to 1.59.
- **Blocked** on the owner confirming the billing status and approving the
  run.

**Verification:**
- pytest: 1228 passed, exit 0;
- static checks: exit 0;
- corpus re-verified;
- live `lexflow` unchanged;
- preserved files intact;
- HEAD `10a44c5`.

No model call, no commit, no push.

---

## Milestone 8 revised (synthetic judgments only); Batch 5 begun (2026-10-26)

**Milestone 8:**
- `scripts/evaluate_analysis_real.py` now uses only SYNTHETIC judgments.
- Each judgment must come from source `lexflow-synthetic` and have a content
  hash listed in the synthetic manifest (`"synthetic": true`). A final gate
  refuses any non-synthetic passage before both plan and execution.
- The smoke-notice hash is pinned.
- `--without-genuine` is removed.
- Plan-only by default.
- **New plan:** `f007eb87a79bf87af67da05e43c8707a87776241b7bbc6fda9bb464921963d29`.
  - 21 runs, at most 63 calls;
  - about USD 0.10 likely, 1.58 at most.
- **Prompt scan:** 49,600 characters checked for 50 genuine-corpus markers;
  0 found.
- Tests: 6.
- The approval request is updated.
- **No model call.**

**Batch 5 (`docs/verification/batch5/BATCH5_REPORT.md`):**
- **Milestone 9 defect fixed:** the synthetic-only assessment could use a
  genuine judgment from `lexflow_e2e`. A new `genuine-precedents` gate
  answers "insufficient"; the scripted wording is corrected; 2 tests added.
- **Milestone 10:** `DEMO_GUIDE.md` §6 and the README status are corrected
  for the genuine corpus. The reproducibility gap (no corpus re-fetch
  script) is recorded.

**Verification:**
- pytest: 1232 passed;
- static checks: exit 0;
- Phase 7 mutation checks: 25 of 25 caught;
- `evaluate_assessment`: 24 of 24;
- corpus re-verified;
- live `lexflow` unchanged;
- preserved files intact;
- HEAD `10a44c5`.

No commit, no push.

---

## Batch 5: corpus integrity, genuine-judgment path, release checklist (2026-10-27)

**Corpus integrity:**
- New `server/scripts/verify_corpus_integrity.py`. It is read-only and never
  downloads or modifies anything.
- New lock `docs/verification/batch2/corpus-sci-tm-v2.lock.json`, written
  once and only for the approved manifest `4b3134b7…`.
- Result: 17 judgments, 0 problems, including the database cross-check.
- Tests: `tests/test_corpus_integrity.py` (8).

**Milestone 8:**
- The harness gains an opt-in `--judgments genuine`. It is checked against
  the corpus lock and states its scope.
- The default synthetic plan is **unchanged**: `f007eb87…`.
- The genuine plan `d106434b…` is built, **not approved**.
- Harness tests: 8.

**Outcome assessment:** still off by default and synthetic-only.

**Release-readiness checklist:** completed in `BATCH5_REPORT.md`. Not
release-ready; blockers listed.

**Verification:**
- pytest: 1242 passed, exit 0;
- static checks: exit 0;
- corpus integrity: 0 problems;
- live `lexflow` unchanged;
- preserved files intact;
- HEAD `10a44c5`.

No model call, no commit, no push.

---

## Milestone 8: synthetic-only real-model run (2026-10-27)

**Approval:** owner-approved plan `f007eb87…` on the free tier. Re-verified
before the run: hash, data scope (0 genuine passages) and provider settings.

**Calls:** 21 runs and 21 calls.
- 9 completed;
- 12 failed with `provider-unavailable` (Google HTTP 5xx; no retry in the
  harness);
- 19,783 input and 5,850 output tokens.

**Results** (completed runs):
- planted contradictions found 6 of 6;
- injected instructions not followed 5 of 5, and flagged every time;
- no false contradiction (S5, 0 of 2);
- 0 items removed by validation.

**Not measured:** S4, S6 and S7 (all runs failed). Recorded in
`REAL_MODEL_APPROVAL_REQUEST.md` and `BATCH4_REPORT.md`. Not evidence of
legal accuracy.

**Checks:**
- related tests: 236 passed;
- corpus integrity: 17 judgments, 0 problems, database cross-check passed;
- live `lexflow` unchanged;
- preserved files intact;
- HEAD `10a44c5`.

No commit, no push. The genuine-judgment plan was not run.

---

## Milestone 8: bounded retries; correction (2026-10-27)

**Correction to the previous entry:** the first run completed **8** runs
and failed **13**, not 9 and 12. The per-scenario results were right; the
totals were miscounted.

**Retries:** `--retry-failed` (plan `f007eb87…` unchanged).
- transient failures only;
- at most 3 attempts per run;
- back-off of 30 s, then 60 s;
- ledger-enforced 63-call ceiling;
- per-attempt HTTP status and error kind recorded.

**Results:**
- 7 of 13 failed runs recovered; **15 of 21 complete**; 41 calls.
- 6 runs remain incomplete (HTTP 503 or 504): S3 #2, S4 #2–3, S5 #3,
  S6 #1 and #3.
- Combined: planted contradictions 11 of 11; injection not followed 5 of 5;
  no false contradiction; correct insufficiency (S4, 1 run); missing
  exhibit not invented (S6, 1 run); no precedent when none was available
  (S7, 3 of 3); 0 items removed by validation.

**Tests:** 2 added for the retry mode (10 harness tests). Results recorded
in `REAL_MODEL_APPROVAL_REQUEST.md` and `BATCH4_REPORT.md`.

No commit, no push.

---

## Batch 5 handoff (2026-10-27)

**Gemini:** stopped at the owner's request. No further model calls.
Preserved: 15 completed results, 13 original failures, the ledger (41
calls), and a plan stamp (`f007eb87…`).

**Fix:** the genuine-judgment evaluation shared the synthetic results
folder. It now has its own folder (`var/eval/real-model-genuine/`), and
execution refuses a folder stamped with another plan. Tests: 2 added (12
harness tests).

**Documentation:**
- corpus-integrity usage, tests and re-acquisition;
- evaluation scopes;
- the six incomplete runs recorded as infrastructure failures (HTTP
  503/504), not model failures.

Both in `INGESTION_AND_EVALUATION.md` §4–5; checklist row updated.

**Verification:**
- pytest: 1246 passed, exit 0;
- static checks: exit 0;
- `npm run check`: 212 passed, build OK;
- corpus integrity: 0 problems, database cross-check passed;
- live `lexflow` unchanged;
- Docker volumes untouched;
- preserved files intact;
- HEAD `10a44c5`.

No commit, no push.

## Pre-commit corrections (2026-10-27)

Requested by the owner after the read-only final review. No commit, no
push, nothing staged.

**Round 1:**
- Phase 7 `mutation-report.md` and `mutation-output.log` restored to
  `10a44c5`. The newer run (25 of 25 caught) stays in
  `batch5/logs/phase7-mutation-checks.txt`.
- README: two stale statements corrected. 17 genuine judgments exist only in
  the isolated `lexflow_e2e`; the retrieval evaluation used model-generated
  and citation-proxy labels; licensing for wider use is unsettled.
- `sci-download.py` excluded locally (`.git/info/exclude`). Its URL and
  SHA-256 are added to `batch2/source-evidence/evidence-manifest.json`.
  Correction: the review said this entry already existed; it did not.
- Phase 5 mutation checks: stopped at C-1 (exit 3; its search text
  occurred three times in `config.py`) after 17 of 65, all caught
  (`batch5/logs/phase5-mutation-checks.txt`).

**Round 2:**
- C-1's search text in `docs/verification/phase5/run_mutation_checks.py`
  now includes the preceding line. Dry run: 65 of 65 search texts found
  exactly once.
- Phase 5 mutation checks, `--working-tree --label batch5`: **65 of 65
  caught**, exit 0 (`batch5/logs/phase5-mutation-checks-2.txt`; report
  `phase5/mutation-report-working-tree-batch5.md`). All 358 source files
  were hash-identical before and after. Earlier reports were not
  overwritten.
- `escr-search.html`: **no redaction made.** The "expired anti-forgery
  token" reported in the review was a false positive: the pattern matched
  a commented-out `csrf-magic.js` script reference. The `app_token` field
  is empty. The other long strings are CAPTCHA cache-busters that the page
  regenerates with `Math.random()`. The file is unchanged (SHA-256
  `1e197d48…`).

**Verification:**
- pytest: 1246 passed, exit 0 (`batch5/logs/pytest-precommit.txt`);
- ruff, format, mypy, OpenAPI check: exit 0
  (`batch5/logs/static-checks-precommit.txt`). The same log shows 11 lint
  findings and one formatting difference in `run_mutation_checks.py`. That
  file is outside the server lint scope, and the same findings exist at
  `10a44c5`.
- `npm run check`: 212 passed, build OK
  (`batch5/logs/npm-check-precommit.txt`);
- Playwright: not rerun (no app change since Batch 3).
- Corpus integrity: 17 judgments, 0 problems, database cross-check passed.
- Live `lexflow` (read-only): 0012 | 7 cases | 6 clients | 7 users | 32
  documents | 3 judgments; no `judgment_provenance` table.
- Docker volumes: all three present.
- `DEVELOPMENT_BRIEF.md`: hash verified.

## Final safeguards before commit (2026-10-27)

- `batch3/logs/pytest.txt` line 24: the Windows home-directory prefix
  (`C:/Users/<username>`) replaced with `<home>`, one occurrence. The rest of
  the historical output is unchanged.
- `phase5/run_mutation_checks.py`: Ruff findings compared with `10a44c5`
  using the server configuration. They are identical: the same 11 findings,
  by rule and source line (E501 ×6, S603, S607 ×2, S602, RUF001), and the
  same 20-line formatting difference. All are pre-existing; the C-1 change
  adds none. The file is outside the server lint scope, and nothing was
  refactored.
