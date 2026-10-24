# Phase 6 execution log — Lawyer review and case brief export

Append-only record of the Phase 6 work. Earlier entries are not rewritten;
corrections are appended. Plan: `docs/PHASE6_PLAN.md`. Checkpoint:
`docs/verification/phase6/checkpoint.json`. The Phase 5 history is in
`docs/PHASE5_EXECUTION_LOG.md`.

## B0 — Preflight and plan (2026-10-25)

- **Start state (verified):** branch `master`, HEAD `5302e41` ("Phase 5:
  close acceptance criteria"; parent `81e8e8c`), working tree clean, no
  remote. `docs/DEVELOPMENT_BRIEF.md` SHA-256
  `274ecaed93400f51dd47c42337fbd6e101aa6be366b80d977d1522359b34c2ec`
  (matches). Docker: `lexflow-db-1` healthy. Ports 5173, 5174, 8000 and
  8001 are free (the API, worker and Vite are not running).
- **Requirements:** the brief, Phase 6:
  - accept, reject or edit each finding, with an optional note;
  - record review actions on the matter timeline;
  - export a case brief (PDF or DOCX) containing only accepted findings,
    with citations.

  It is done when unreviewed findings are visibly marked as unreviewed and
  the export contains only accepted findings. A search of the repository
  found no separate lab or experiment specification, so the brief is the
  source.
- **Architecture read:**
  - `authz.py` (actions and relations; `load_case`);
  - `analysis_runs` and its validated `result`, where finding ids are
    unique within a run;
  - `audit.py`;
  - `timeline_events`, which are shown to staff and never to clients, and
    whose 30 most recent rows the evidence builder sends to the model
    (`TIMELINE_MAX`);
  - the client portal, which shows no timeline;
  - the AnalysisTab and its hooks.
  - `python-docx` 1.2.0 is already a declared dependency. Latest
    migration: 0011.
- **Plan and decisions:** `docs/PHASE6_PLAN.md` (D6-1 … D6-9, AC1–AC10).
  The main privacy decision is D6-5: review actions reach the matter
  timeline as entries derived from the review history, not as
  `timeline_events` rows, so they can never become model input.
- **Records created:**
  - `CLAUDE.md`, the instructions for future sessions, with the resume
    command;
  - `docs/PHASE6_PLAN.md`;
  - this log;
  - `docs/verification/phase6/README.md`;
  - `docs/verification/phase6/checkpoint.json`;
  - `docs/verification/phase6/update_checkpoint.py`, the atomic, validating
    checkpoint updater.
- **No session hook was added:** Claude Code loads `CLAUDE.md`
  automatically, which shows the resume procedure. A hook would add
  configuration without adding safety, and the files remain the source of
  truth.
- **Test baseline (historical, not re-run in B0):** at `5302e41`, Phase 5
  M10.4 recorded pytest 980 passed, Vitest 180 passed with the build, and
  Playwright 41 passed, all exit 0. Fresh runs follow per batch.
- **Boundaries:** no push, deployment or real or paid model call; no change
  to application records; no destructive migration; the brief stays
  unchanged.

Checkpoint: Batch 0 — preflight, plan and records done; next action: Batch 1, add the review models and additive migration 0012 (`server/lexflow/models.py`, `server/migrations/versions/0012_finding_reviews.py`) with model and migration tests.

## B1 — Review models and migration 0012 (2026-10-25)

- **Files changed:**
  - `server/lexflow/domain.py`: `ReviewStatus`, `FindingKind`,
    `FINDING_PREFIX` and the length limits (2,000 each for the reviewed
    wording and the note).
  - `server/lexflow/models.py`: `AnalysisFindingReview` (the current state)
    and `AnalysisFindingReviewEvent` (the append-only history).
  - `server/migrations/versions/0012_finding_reviews.py` (new).
  - `server/tests/test_migrations.py`: the expected tables now include the
    two new ones.
  - `server/tests/review_fixtures.py` (new): a SYNTHETIC ready run with one
    finding of each kind.
  - `server/tests/test_finding_reviews_model.py` (new).
- **Schema (additive only):** two new tables; no existing table, column or
  row changes. Enforced by the database:
  - the status must be `unreviewed`, `accepted`, `edited` or `rejected`;
  - the kind must be fact, issue, precedent or contradiction, and must match
    the id prefix (F, I, P or C);
  - the id format is `^[FIPC][1-9][0-9]{0,3}$`;
  - wording is present exactly when the status is `edited`;
  - wording and note are 1–2,000 characters (an empty note is stored as
    NULL);
  - the version is at least 1;
  - a review is unique per (run, finding id); a history entry is unique per
    (review, version);
  - foreign keys cascade with the case and run, and become NULL when the
    user is removed.
  - One foreign key is named explicitly, because the generated name would
    exceed PostgreSQL's 63-character limit.
  - The downgrade drops both tables; this is documented in the migration.
- **Migration applied:** only to scratch test databases (by
  `tests/test_migrations.py`) and to `lexflow_test` (by the suite's setup).
  **`lexflow` is unchanged, still at 0011.**
- **Tests (fresh):**

  | Command (from `server/`) | Result | Exit |
  |---|---|---|
  | `pytest -q -p no:cacheprovider tests/test_migrations.py` | 5 passed (round trip to head and back; models match the migrations; existing data survives) | 0 |
  | `pytest -q -p no:cacheprovider tests/test_finding_reviews_model.py` | 16 passed (the result is unchanged by a review; 12 kinds of inconsistent row refused; one review per finding per run, so the same id in another run is another finding; a history entry is unique per version; the run must exist) | 0 |
  | `ruff check migrations lexflow tests`; `mypy` (140 files) | clean | 0 |

  - The first run of `test_migrations.py` failed (1 of 5) because its
    expected-table list did not include the new tables. The list was
    updated and the rerun passed.

Checkpoint: Batch 1 — review models and migration 0012 done (tests pass; live database unchanged); next action: Batch 2, review service and API (`server/lexflow/services/reviews.py`, `server/lexflow/api/analysis.py`, `server/lexflow/authz.py` `REVIEW_ANALYSIS`, `server/lexflow/schemas.py`) with tests in `server/tests/test_analysis_reviews.py`.

## B2 — Review service, API, audit and timeline (2026-10-25)

- **Files changed:**
  - `server/lexflow/services/reviews.py` (new): reading findings from a
    stored result; `apply` (locks the row, checks the version, writes the
    current state and a history entry in one transaction, and returns
    without writing when nothing changes); `history`; `summary`;
    `timeline_entries`; `table_exists`.
  - `server/lexflow/api/reviews.py` (new):
    - `GET /api/cases/{id}/analysis-runs/{run_id}/reviews`;
    - `PUT …/reviews/{finding_id}`;
    - `GET …/reviews/{finding_id}/history`.
  - `server/lexflow/main.py`: the router is mounted with the staff routers,
    so clients are refused.
  - `server/lexflow/authz.py`: `Action.REVIEW_ANALYSIS` (Administrator,
    lead, associate) and the `can_review_analysis` permission.
  - `server/lexflow/schemas.py`:
    - review request and response models;
    - `CasePermissions.can_review_analysis`;
    - `TimelineEventOut.kind` (`case` or `review`).
  - `server/lexflow/services/cases.py`: the case timeline merges the review
    entries derived from the history (D6-5).
  - `server/openapi.json`: regenerated (additive changes only).
  - `server/tests/test_analysis_reviews.py` (new).
- **Behaviour:**
  - Statuses are `accepted`, `edited` (needs wording that differs from the
    AI's), `rejected` and `unreviewed` (clears a decision); wording is
    refused for any status except `edited`.
  - The `expectedVersion` must match, otherwise the answer is 409
    `review-changed`. A request that changes nothing returns the current
    state without a new history entry.
  - A run of another case, an unknown or malformed id, or a finding that is
    not in the run answers 404. A run that is not ready answers 409.
  - An archived case answers 409 `case-archived` to decisions and can still
    be read. Without migration 0012 the answer is 503 `review-unavailable`,
    and the case detail still works.
  - The audit event `analysis.finding_reviewed` holds only the finding, the
    kind, the status, the version, and whether the wording or note changed.
  - The timeline entry reads: "{Kind} {id} of the AI analysis of {date}
    {decision}", with the actor and time, and never the wording or the note.
- **Tests (fresh):**

  | Command (from `server/`) | Result | Exit |
  |---|---|---|
  | `pytest -q -p no:cacheprovider tests/test_analysis_reviews.py` | 12 passed | 0 |
  | `pytest -q -p no:cacheprovider tests/test_analysis_runs.py tests/test_case_access.py` | 111 passed | 0 |
  | `pytest -q -p no:cacheprovider -x` (full suite) | **1008 passed** (980 + 16 + 12) | 0 |
  | `ruff check lexflow tests`; `mypy` (143 files) | clean | 0 |

  The 12 review tests cover:
  - every finding starting unreviewed;
  - the accept → edit → reject → clear history with the result unchanged;
  - the edit rules (blank wording, wording unchanged from the AI's, wording
    on an accept, an invalid status or field, wording too long);
  - stale versions and retries adding no history entry;
  - notes private to reviewers (a paralegal sees the decision without the
    note);
  - ids being per run;
  - who may decide (the Administrator, lead and associate may; a paralegal
    gets 403; outsiders 404; a client 403);
  - archived cases;
  - cross-case, unknown, malformed and not-ready runs and findings;
  - audit details without wording or notes;
  - timeline entries without content, with no new `timeline_events` rows;
  - 503 without migration 0012.
- **Not covered by a test:** two first decisions written at exactly the same
  time. The unique constraint refuses the second (B1 test), and the API maps
  `IntegrityError` to 409. A true concurrent test is not practical in the
  per-test transaction setup.
- **Contract:** additive, so `src/services/api/schema.gen.ts` will be
  regenerated with the UI in B4.

Checkpoint: Batch 2 — review service, API, audit and timeline done (1008 backend tests pass); next action: Batch 3, evidence-isolation tests (`server/tests/test_review_isolation.py`) proving review decisions, notes, wording and timeline entries never reach `evidence.assemble` or `prompt.render`, and that stored run evidence is unchanged.

## B3 — Evidence isolation (2026-10-25)

- **File:** `server/tests/test_review_isolation.py` (new, 4 tests). The
  review design itself needed no code change: D6-5 already keeps review
  actions out of `timeline_events`.
- **What the tests prove:**
  1. After an edit (with a note), a rejection (with a reason) and an
     acceptance (with a note):
     - `evidence.assemble` gives the **same** timeline entries as before
       the reviews;
     - `prompt.render` contains none of the markers: the note, the wording,
       the reason, "AI finding reviewed", "lawyer's wording", "rejected";
     - the matter timeline still shows the three review entries to staff.
  2. A **new analysis started after the reviews**, run through the real
     worker with a recording scripted provider, sends none of those markers
     in the system instruction or the prompt the provider receives.
  3. Reviewing never changes the run's recorded `evidence`, `result` or
     `prompt_version`, and the run's API still shows the model's original
     wording.
  4. *Control:* an ordinary `timeline_events` row carrying the marker
     **does** reach the prompt. The channel is real, so the tests above
     would fail if review actions were ever stored as timeline rows.
- **Results (fresh):**
  - `pytest -q -p no:cacheprovider tests/test_review_isolation.py`:
    **4 passed**, exit 0.
  - `ruff check` and `mypy` (144 files): clean.
- **Audit records:** they are never read by the evidence builder, which
  queries only the case, its timeline rows, its document chunks and the
  judgment collection. Test 2 covers what the provider actually receives.

Checkpoint: Batch 3 — evidence isolation proved (4 tests); next action: Batch 4, the review UI (regenerate `src/services/api/schema.gen.ts`; review hooks and service in `src/hooks/useCaseAnalysis.ts` and `src/services/ai/aiService.ts`; controls in `src/components/workspace/AnalysisTab.tsx`; MSW mocks in `src/test/mockAnalysis.ts`; Vitest in `src/pages/analysis.test.tsx`).

## B4 — Lawyer-review UI (2026-10-25)

- **Files changed:**
  - `src/services/api/schema.gen.ts`: regenerated from `server/openapi.json`.
  - `src/types/ai.ts`: the review types, which are aliases of the generated
    contract.
  - `src/services/ai/aiService.ts`: `reviews`, `review`, `reviewHistory`,
    and `exportBrief` (used in B5).
  - `src/services/api/client.ts`: `apiFetchFile` (a file download with the
    same error handling as `apiFetch`; the file name is sanitised).
  - `src/hooks/useFindingReviews.ts` (new):
    - queries are keyed per run;
    - there is no optimistic state: a decision is shown only from the
      server's answer;
    - a 409 fetches the list again;
    - a success refreshes the history and the case timeline.
  - `src/components/workspace/FindingReview.tsx` (new):
    - a status badge on every finding ("Unreviewed", "Accepted", "Edited by
      lawyer", "Rejected");
    - who decided and when;
    - the lawyer's wording beside the AI's original;
    - the reviewer's note, labelled "not in the brief";
    - a warning when a source changed;
    - Accept, Edit wording (a form with a note), Reject (with an optional
      reason), and Clear decision (after a confirmation);
    - "Saving…" while a request runs, and the server's error as an alert;
    - the history, oldest first;
    - `ReviewProgress` ("Lawyer review: n of m findings reviewed …").
  - `src/components/workspace/AnalysisTab.tsx`:
    - a review panel under every fact, issue, precedent comparison and
      contradiction;
    - the progress in the result card;
    - loading and error states, with a retry.
  - `src/test/mockApi.ts`: the `reviewAnalysis` permission and the timeline
    `kind`, mirroring the server.
  - `src/test/mockAnalysis.ts`: the MSW review routes (versions, history,
    notes only for advocates, 503 and 409 helpers).
  - `src/pages/review.test.tsx` (new).
- **Accessibility:**
  - each panel is a labelled region ("Review of Fact F1");
  - the form fields have labels;
  - the controls are real buttons, so they work from the keyboard;
  - alerts use `role="alert"` and progress uses `role="status"`;
  - the badges are text, not colour alone.
- **Permissions in the UI:** the controls are shown only when the server
  says `canReview`. Paralegals see the decisions without controls or notes
  (the server leaves the notes out). Clients never reach the page.
- **Tests (fresh):**

  | Command | Result | Exit |
  |---|---|---|
  | `npx vitest run src/pages/review.test.tsx src/pages/analysis.test.tsx` | 28 passed (9 new) | 0 |
  | `npx vitest run` | **189 passed** (180 + 9), 18 files | 0 |
  | `npm run lint`; `npx prettier --check .`; `npm run typecheck` | clean | 0 |

  The 9 new tests cover:
  - every finding marked Unreviewed;
  - an acceptance shown only after the server has stored it, with the
    reviewer named and the progress updated;
  - a failed save leaving the finding Unreviewed, with an alert;
  - an edit keeping the AI's wording on screen, with the note shown;
  - a rejection with a reason, clearing after confirmation, and the history
    with 2 entries;
  - a 409 when someone else reviewed meanwhile, then the current decision
    shown;
  - the changed-source warning;
  - a paralegal seeing no controls;
  - the 503 message with a retry.

  The first run of the paralegal test failed because `renderApp` has no
  `unmount`; `cleanup()` is used instead, and the rerun passed.

Checkpoint: Batch 4 — review UI done (189 Vitest pass); next action: Batch 5, brief export: `server/lexflow/services/brief.py` (python-docx; only accepted and edited findings, citations, counts, synthetic labels, changed-source flags, disclaimer, no notes), route `GET /api/cases/{id}/analysis-runs/{run_id}/brief` in `server/lexflow/api/reviews.py`, an export button in the UI; tests in `server/tests/test_case_brief.py`.

## B5 — Case brief export (2026-10-25)

- **Format:** DOCX, which the brief allows ("PDF or DOCX"). It is made with
  `python-docx`, which is already a dependency, so nothing new was added.
- **Files changed:**
  - `server/lexflow/services/brief.py` (new): the document builder and the
    counts.
  - `server/lexflow/api/reviews.py`: `GET /api/cases/{id}/analysis-runs/{run_id}/brief`.
    Access needs `view` on the case. With no accepted finding the answer is
    409 `no-accepted-findings`; without migration 0012 it is 503. The
    response has `Content-Disposition: attachment` with a sanitised file
    name and `Cache-Control: no-store`. Each export is audited as
    `analysis.brief_exported` with the counts only.
  - `server/lexflow/api/analysis.py`: `_changed` became the public
    `changed_evidence`, which the brief reuses; the test references were
    updated.
  - `server/openapi.json` and `src/services/api/schema.gen.ts`: regenerated.
  - `src/lib/saveFile.ts` (new).
  - `src/components/workspace/FindingReview.tsx`: `ExportBrief`, a button
    that is disabled, with the reason, until a finding is accepted; it shows
    the saved file name or the server's error.
  - `src/components/workspace/AnalysisTab.tsx`: shows the button next to the
    review progress.
  - `src/test/mockAnalysis.ts`: the brief route.
  - Tests: `server/tests/test_case_brief.py` (new) and
    `src/pages/review.test.tsx` (3 more).
- **Brief content** (checked by opening the generated DOCX):
  - a title, the case number, court, practice area, status and opposing
    party;
  - "Prepared" with the date, the user, the run's date, provider, model,
    prompt version and validation version;
  - a "Review status" section: "This brief contains only the N findings a
    lawyer accepted (M in the lawyer's own wording). Not included: X
    unreviewed and Y rejected.", plus "Review is not complete…" when X > 0.
    The brief is never called "approved";
  - sections for Facts, Legal issues, Precedent comparisons and
    Contradictions, with only accepted and edited findings. An edited
    finding appears in the lawyer's wording, marked "Wording by the
    reviewing lawyer". Each finding has:
    - its citation (document, page or part, and the verified quote; or the
      judgment's title, court, citation, year and compared passage);
    - "SYNTHETIC test judgment: fictional, not real case law." for
      synthetic judgments;
    - a flag when its source changed (a separate wording for a judgment
      passage);
    - for an issue, the facts it rests on, with "(not in this brief)" for
      facts that were not accepted;
    - "Accepted … by <name> on <date>".
  - the disclaimer.
  - Never included: notes, internal UUIDs, or the brief's own author name
    (the document property is "LexFlow").
- **Fix found while reviewing a generated brief:** the changed-source note
  for a precedent spoke of "the quote", which a precedent comparison does
  not show. It now has its own wording, `PASSAGE_CHANGED_NOTE`, and the
  tests check both notes.
- **Tests (fresh):**

  | Command | Result | Exit |
  |---|---|---|
  | `server: pytest -q -p no:cacheprovider tests/test_case_brief.py` | 10 passed | 0 |
  | `server: pytest -q -p no:cacheprovider tests/test_analysis_runs.py tests/test_analysis_reviews.py` | 52 passed (after the rename) | 0 |
  | `npx vitest run` | **192 passed** (189 + 3), 18 files | 0 |
  | `ruff`, `mypy` (146 files), `prettier --check .`, eslint, `npm run typecheck` | clean | 0 |
  | `export_openapi.py --check`; `npm run api:check` | up to date | 0 |

  The 10 brief tests cover:
  - only accepted findings, with the counts and the disclaimer;
  - citations and reviewers;
  - no notes or internal ids anywhere in the file;
  - changed sources flagged, not replaced;
  - unchanged sources unflagged;
  - an issue naming the facts left out;
  - 409 with nothing accepted;
  - who may export (Administrator, lead, associate, paralegal: yes;
    outsiders 404; a client 403);
  - a safe file name;
  - an audit event with counts only, and no new run created (no model
    call).

  The 3 UI tests cover: the button disabled with its reason; a download
  with the saved file name; the server's refusal shown.

Checkpoint: Batch 5 — brief export done (10 backend + 3 UI tests); next action: Batch 6, integration and edge cases: an e2e test (`e2e/review.spec.ts`: review a scripted run and export the brief through the real API and worker), plus backend edge-case tests (a newer run does not inherit reviews; a document re-extracted after review flags the brief; a document deleted after review).

## B6 — Integration and edge cases (2026-10-25)

- **Files changed:**
  - `server/tests/test_review_lifecycle.py` (new, 6 tests, on runs made by
    the real worker with the scripted provider and real extracted
    documents).
  - `e2e/analysis.spec.ts`: a new test, "a lawyer reviews the findings and
    exports a brief of the accepted ones (Phase 6)", and the paralegal test
    now checks the review states.
  - `src/components/workspace/OverviewTab.tsx`: review entries on the
    matter timeline carry a "Lawyer review" tag.
  - `src/components/workspace/AnalysisTab.tsx`: **defect found and fixed.**
    The Analysis Inputs panel said "{all timeline entries} events (the
    latest 30 are sent)". With review entries merged into the timeline, that
    count would have included decisions that are never sent. It now counts
    only case events and says "lawyers' review decisions never are"; a
    Vitest test covers it.
  - `src/pages/review.test.tsx`: 1 more test.
- **Edge cases checked** (`test_review_lifecycle.py`):
  1. A worker run is reviewed and exported, and its live sources are not
     flagged.
  2. Re-extraction after review: the brief flags the source, and the
     decision, its version and the run's result stay unchanged.
  3. A deleted document: flagged, not replaced, with the citation kept as
     verified.
  4. A newer run starts fully unreviewed. The older run keeps its decisions
     and can still be exported.
  5. Revoked access: the removed associate gets 404 for reading and
     deciding, and their earlier decision stays attributed to them.
  6. A failure after the rows were written but before the commit (raised
     inside the savepoint): no review row, no history entry and no audit
     event remain. The 500 answer does not contain the internal error text.
  - Already covered elsewhere:
    - repeated and concurrent changes (B2: version 409, no-op retries, the
      unique constraints);
    - reused ids across runs (B1, B2);
    - a judgment removed after analysis (B5: its passage is flagged with a
      separate note);
    - an archived case (B2);
    - unauthorised cross-case requests (B2, B5);
    - Phase 5 runs never changed (B1, B3).
- **E2E** (`npx playwright test e2e/analysis.spec.ts`, database
  `lexflow_e2e` recreated by `e2e.py prepare`, scripted provider): **4
  passed**, exit 0. The new test:
  - checks that F1 is Unreviewed and that the export button is disabled
    until something is accepted;
  - accepts F1;
  - edits P1's wording, which is then shown as "Edited by lawyer";
  - exports the brief: a download named `case-brief-LF-….docx`, beginning
    with the zip signature `PK`;
  - checks that the Overview timeline shows the "Lawyer review" entry.
  The paralegal then sees "Accepted" on F1 and no review buttons.
- **Other results (fresh):**
  - `server: pytest -q -p no:cacheprovider tests/test_review_lifecycle.py`:
    6 passed, exit 0.
  - `npx vitest run src/pages/review.test.tsx`: 13 passed, exit 0.
  - ruff, mypy (147 files), eslint, prettier and typecheck: clean.

Checkpoint: Batch 6 — integration, edge cases and e2e done (6 lifecycle tests, 4 e2e tests); next action: Batch 7, full verification: backend pytest, ruff, format, mypy (also for Linux), `alembic check` on `lexflow_test`, OpenAPI and API-type drift, `npm run check`, full Playwright, and a Phase 6 mutation runner (`docs/verification/phase6/run_mutation_checks.py`); logs in `docs/verification/phase6/`.

## B7 — Full verification (2026-10-25)

All runs below are fresh, on the Phase 6 working tree (HEAD `5302e41` plus
the uncommitted Phase 6 changes).
- Databases: `lexflow_test`, recreated by the pytest setup (its URL guard
  needs "test" as a whole name part and refuses `dbname`/`service`); the
  scratch migration databases, created and dropped by their tests; and
  `lexflow_e2e`, recreated by `e2e.py prepare`.
- **`lexflow` was not used by any check.**
- No real model call: tests use fakes, and e2e uses the scripted provider.

| Check | Command | Result | Exit |
|---|---|---|---|
| Backend tests | `server: python -m pytest -q -p no:cacheprovider` | **1028 passed**: 980 from Phase 5 plus 48 new (16 model, 12 review API, 4 isolation, 10 brief, 6 lifecycle); 0 skipped (`docs/verification/phase6/pytest-full.log`) | 0 |
| Lint and format | `server: ruff check .`; `ruff format --check .` | clean; 162 files formatted | 0 / 0 |
| Types | `server: mypy`; `mypy --platform linux .` | 147 / 159 files, no issues | 0 / 0 |
| Migrations vs models | `alembic check` on `lexflow_test` at head 0012 (URL asserted) | no new upgrade operations | 0 |
| API contract | `server: python scripts/export_openapi.py --check`; `npm run api:check` (inside `npm run check`) | up to date | 0 |
| Front end | `npm run check` (eslint, prettier, tsc, api:check, sample-data:check, vitest, build) | 18 files, **193 tests passed**; build OK (`npm-check.log`) | 0 |
| End to end | `npx playwright test` | **42 passed** (41 + the new review-and-export test) (`playwright.log`) | 0 |
| Mutation | `server\.venv\Scripts\python docs/verification/phase6/run_mutation_checks.py` (new runner, 19 guards) | **19 of 19 caught**; every file restored, with target SHA-256 values checked (`mutation-report.md`, `mutation-output.log`) | 0 |

- **The 19 mutations:**
  - P6-1 to P6-6: stale version, no-op retry, unchanged edit, not-ready run,
    another case's run, unknown finding;
  - P6-7 and P6-8: paralegal permission, note visibility;
  - P6-9 and P6-10: no note in the audit or on the timeline;
  - P6-11 to P6-15: only accepted findings in the brief, the lawyer's
    wording, the synthetic label, the changed flag, no export without an
    accepted finding;
  - U6-1 to U6-4: controls only when allowed, the Unreviewed label, export
    disabled until something is accepted, review entries not counted as
    analysis input.
  - All exited with test failures (exit 1); none survived.
- **Log hygiene:** the new logs contain no home paths, real keys or database
  URLs.
- **Not run:** the Phase 5 mutation runner. Its targets did not change in
  Phase 6, except `api/analysis.py` (the `_changed` rename, whose anchor
  M9-9 is unchanged), `services/cases.py` and `AnalysisTab.tsx`. Its dry run
  is in B8.

Checkpoint: Batch 7 — full verification passed (pytest 1028, Vitest 193 + build, Playwright 42, mutation 19/19, static and contract checks clean); next action: Batch 8, the D6-9 decision on migrating the live database, ADR 0020, SRS and traceability updates, the verification README, a Phase 5 mutation dry run, plan and checkpoint reconciliation, then the closure commit.

## B8a — D6-9: migration 0012 on the live database (2026-10-25)

- **Decision:** apply 0012 to `lexflow`. It is not needed for acceptance
  (without it the review routes answer 503 and nothing else changes), but
  it is needed for the owner to use Phase 6 in the local app. 0012 only
  creates two tables. It was authorised for this session, subject to an
  inspected target and a verified backup.
- **Inspection (read-only):** target `127.0.0.1:5432/lexflow`, confirmed by
  `current_database()`; no URL query parameters; `alembic_version` 0011; 0
  other sessions; no review tables.
- **Backup:** `server/var/backups/lexflow-20261025-043125-pre-0012.dump`
  (git-ignored), made with `pg_dump -Fc` inside the container, without
  overwriting anything. It is 108,340 bytes, SHA-256
  `f55168ca074439518fff26c4836d9048121b5a0b8cc5ecb55411ce4e9c01a49e`, and
  readable (`pg_restore --list`: 132 entries, 21 table-data entries).
- **Restore check:** restored with `--exit-on-error` into the **new**
  database `lexflow_pre0012_verify` (on the same server; nothing else was
  touched). A row-level comparison (count plus an md5 over the sorted row
  md5s, per table; a read-only script kept outside the repository) found
  live and restore **identical**: 21 tables, 310 rows. The verification
  database is kept; deleting it is the owner's decision, as in M8.
- **About to run:**
  `server: PGOPTIONS="-c lock_timeout=10s" .venv\Scripts\python -m alembic upgrade head`.
  Expected: "Running upgrade 0011 -> 0012"; the two new tables; every
  existing row unchanged. If it is interrupted, check `alembic_version` and
  `to_regclass('analysis_finding_reviews')` before retrying.
- **Result:**
  - `alembic upgrade head` printed "Running upgrade 0011 -> 0012" and exited
    0.
  - `alembic current`: **0012 (head)**. `alembic check` against `lexflow`:
    "No new upgrade operations detected".
  - `analysis_finding_reviews` and `analysis_finding_review_events` each
    have 12 columns and 0 rows (22 and 23 constraints in
    `information_schema`, counting NOT NULL checks).
  - Row-level comparison, live now against live before the migration: the
    only differences are the `alembic_version` value and the two new tables,
    so there are **0 unexpected differences** and every row of the 21
    earlier tables (310 rows) is unchanged.
- **Recovery, if ever needed:** `alembic downgrade 0011` (drops only the two
  review tables; exercised on scratch databases by `test_migrations.py`), or
  the backup above. Neither was run.
- **Not changed:** no application record was imported, deleted or modified,
  and no API or worker was running.

## B8 — Records reconciled; Phase 6 closed (2026-10-25)

- **Records updated:**
  - `docs/PHASE6_PLAN.md`: status "complete", D6-9 marked done, §9 resume,
    and a new §10 with limitations and deferred items.
  - `docs/adr/0020-lawyer-review-and-case-brief.md` (new), with
    `docs/adr/README.md` gaining the rows for 0019 (missing since Phase 5)
    and 0020.
  - `docs/SRS.md`: version Phase 6, the scope paragraph, FR-19 marked done,
    and the out-of-scope list.
  - `docs/TRACEABILITY.md`: FR-19 row.
  - `docs/ARCHITECTURE.md`: use case uc14, "Review AI findings and export a
    case brief", for the Administrator and Advocate.
  - `docs/verification/phase6/README.md`: results and tests by criterion.
  - `CLAUDE.md`: Phase 6 closed and Phase 7 gated.
  - The checkpoint.
- **Phase 5 tooling still valid:**
  `docs/verification/phase5/run_mutation_checks.py --dry-run` found 65 of
  65 snippets exactly once (Phase 6 touched three of its target files
  without moving an anchor).
- **Acceptance criteria:**
  - AC1, AC2: B1, B2 and B6.
  - AC3: B3.
  - AC4: B4 and B6.
  - AC5–AC7: B5 and B6.
  - AC8: B7.
  - AC9: this entry.
  - AC10: the closure commit "Phase 6: lawyer review and case brief
    export", whose parent is `5302e41`. Its hash is recorded by git (and in
    the final report), not in this log, so the tree stays clean.
- **Brief requirements:** "for each finding: accept, reject, or edit, with
  an optional note" is met (B2, B4); "record review actions on the matter
  timeline" is met (B2 and the Overview tag, B6); "export a case brief (PDF
  or DOCX) containing only accepted findings, with citations" is met as a
  DOCX (B5). Done when:
  - "unreviewed findings are visibly marked as unreviewed": met (B4, the
    U6-2 mutation, e2e);
  - "the export contains only accepted findings": met (B5, the P6-11
    mutation).
- **Boundaries:**
  - no push, deployment or remote change;
  - no real or paid model call;
  - no application record imported, deleted or modified;
  - one additive migration (0012) applied to `lexflow`, after a verified
    backup;
  - no destructive operation; no database dropped (the verification
    database `lexflow_pre0012_verify` was created and kept);
  - the brief stays unchanged;
  - no Phase 7 work and no real-judgment acquisition.
- **Deferred, not Phase 6:**
  - the real judgment source (dataset phase: verified reuse terms,
    provenance, separation from synthetic demo data and evaluation
    fixtures);
  - Phase 7 thresholds;
  - how long to keep the backups and verification databases (owner).

Checkpoint: Batch 8 — Phase 6 COMPLETE (closure commit "Phase 6: lawyer review and case brief export" on 5302e41); next action: none in Phase 6; Phase 7 (gated) starts only on the owner's instruction.
