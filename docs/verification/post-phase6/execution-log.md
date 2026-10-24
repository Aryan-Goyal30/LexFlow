# Post-Phase-6 verification and Phase 7 readiness — execution log

Append-only record of the review that followed the Phase 6 closure. It does
not change the Phase 5 or Phase 6 records. Checkpoint: `checkpoint.json` in
this folder. Scope: verification and planning only. Phase 7 is not
implemented here.

## V0 — Baseline (2026-10-25)

- **Repository:** root `C:/Projects/Claude/Legal Case Management System`,
  branch `master`, HEAD `eada4ef5c1ad77efa5d3b50f05d40cb25fe0cae9`
  ("Phase 6: lawyer review and case brief export", 2026-10-25 04:35:42
  +0530). Its parent is `5302e411dcf93a4651e036c8428a8d691f9e252b`, as
  reported, and `eada4ef` is in the current history. Working tree clean (0
  entries). No remote.
- **Protected brief:** `docs/DEVELOPMENT_BRIEF.md` SHA-256
  `274ecaed93400f51dd47c42337fbd6e101aa6be366b80d977d1522359b34c2ec`,
  which matches.
  - *Observation:* the file is excluded by the local `.git/info/exclude`.
    It is **not under version control**, so its integrity rests on the
    recorded hash alone.
- **Records read:**
  - `CLAUDE.md`;
  - `docs/PHASE6_PLAN.md`, `docs/PHASE6_EXECUTION_LOG.md` (sections B0–B8,
    B8a, ending in a `Checkpoint:` line that agrees with the checkpoint),
    `docs/verification/phase6/checkpoint.json` (status COMPLETE) and its
    README;
  - the Phase 5 plan, log and checkpoint;
  - `server/migrations/versions/0012_finding_reviews.py`: additive (two
    `create_table` calls and two indexes); the downgrade drops only those
    tables.
- **Recorded Phase 6 evidence** (all committed in `eada4ef`):
  - `pytest-full.log`: 1028 passed, exit 0;
  - `npm-check.log`: 18 files, 193 tests, build OK, exit 0;
  - `playwright.log`: 42 passed, exit 0;
  - `mutation-report.md`: 19 of 19 caught, run 2026-10-24 22:57 UTC on the
    working tree before the commit.
- **Gaps in the evidence (no defect implied):**
  1. The ruff, mypy, alembic and OpenAPI results exist only as entries in
     the execution log; there are no log files.
  2. The checkpoint's AC4 note still says "review.test.tsx 9 passed",
     although the file ended with 13 tests (B6). The total of 193 is right.
  3. The recorded runs used the working tree just before the commit. That
     the committed code is what was verified is checked by the fresh runs in
     V1.

## V1 — Phase 6 evidence rechecked with fresh runs (2026-10-25)

All runs below were on HEAD `eada4ef`, with a clean tree apart from this
folder.
- Database targets were checked from the URLs (host, port and name only):
  the app uses `127.0.0.1:5432/lexflow` and the tests
  `127.0.0.1:5432/lexflow_test`; neither has query parameters, and
  `PGDATABASE`/`PGSERVICE` are unset.
- `lexflow_test` is recreated by the pytest setup, whose guard needs "test"
  as a whole name part. `lexflow_e2e` is recreated by `e2e.py prepare`.
  **`lexflow` was not used.**

| Check | Command | Fresh result | Exit | Evidence |
|---|---|---|---|---|
| Backend tests | `server: python -m pytest -q -p no:cacheprovider` | **1028 passed** (same as recorded) | 0 | `pytest-full.log` |
| Lint and format | `ruff check .`; `ruff format --check .` | clean; 162 files | 0 / 0 | `static-checks.log` |
| Types | `mypy`; `mypy --platform linux .` | 147 / 159 files, no issues | 0 / 0 | `static-checks.log` |
| API contract | `python scripts/export_openapi.py --check` | up to date | 0 | `static-checks.log` |
| Migrations vs models | `alembic check` on `lexflow_test` (URL asserted) | no new upgrade operations | 0 | `static-checks.log` |
| Front end | `npm run check` | 18 files, **193 tests passed**, build OK (same as recorded) | 0 | `npm-check.log` |
| End to end | `npx playwright test` | **42 passed**, including "a lawyer reviews the findings and exports a brief…" (same as recorded) | 0 | `playwright.log` |
| Mutation | the Phase 6 runner loaded with its output folder set to this folder, so the committed Phase 6 report is untouched | **19 of 19 caught**, all files restored | 0 | `mutation-report.md`, `mutation-output.log` |

- **Conclusion:** the committed code reproduces every recorded Phase 6
  result. Gap 1 of V0 (no log files for the static checks) is closed by
  `static-checks.log`. Gap 2 (the AC4 note) is a cosmetic slip in the
  checkpoint text; the Phase 6 records are not edited.

## V2 — Local application and database readiness (2026-10-25)

- **Target (from the URL; no credentials shown):** `127.0.0.1:5432/lexflow`,
  no query parameters, `PGDATABASE`/`PGSERVICE` unset. Docker
  `lexflow-db-1` is healthy.
- **Read-only checks on `lexflow`:**
  - `alembic current`: **0012 (head)**.
  - Row-level comparison (count plus an md5 of the sorted row md5s per
    table) against the state saved just before the 0012 migration: the only
    differences are the `alembic_version` value and the two new review
    tables, both with **0 rows**. All other data is identical (21 tables,
    310 rows), so no review has been recorded on `lexflow` yet.
- **Backup and verification database (kept; not touched):**
  - `server/var/backups/lexflow-20261025-043125-pre-0012.dump` is present,
    SHA-256 `f55168ca…c01a49e`, matching the record.
  - `lexflow_pre0012_verify` is present.
  - Also present: `lexflow_p3_restore` and `lexflow_restore_check`, older
    restore databases from earlier phases. How long to keep them is the
    owner's decision.
- **Start-up check:** `server: .venv\Scripts\python -m lexflow`, as
  documented in `server/README.md`. Start-up only reads (a user count for
  the production refusal).
  - `GET /api/health` returned 200 `{"status":"ok","database":"ok"}`.
  - Anonymous `GET …/reviews` and `GET …/brief` returned **401**.
  - The OpenAPI document lists `/reviews`, `/reviews/{finding_id}`,
    `/reviews/{finding_id}/history` and `/brief`.
  - No sign-in was made, because a sign-in would write a session row. The
    process was stopped afterwards (PID 39888, its command line confirmed
    as `python -m lexflow`).
  - A second comparison after the probes: still identical, so no writes.
- **Conclusion:** the app starts safely against the intended local database,
  which is at 0012. Signed-in checks against `lexflow` were not run on
  purpose; the functional behaviour is verified on disposable databases
  (V3).
- **Correction to the result above (appended after more runs):**
  - After the probe was reformatted (whitespace only), a 4th run **failed
    the probe's own "B was seen blocked" check**: the watcher did not see B
    waiting within 20 seconds. B was still refused with
    `IntegrityError: UniqueViolation`, and one review and one history entry
    remained. Whether the watcher sees the wait depends on timing, so it is
    not a sound assertion.
  - The probe now asserts only the outcome: B refused (unique violation or
    stale version), and exactly one review and one history entry. The lock
    observation is printed for information only.
  - Runs 5–9 passed (exit 0), each with B blocked and then refused by the
    unique index (`race-probe/probe-output.log`).
  - Across all 9 runs, no second decision was ever stored. Run 4's failure
    was the observation, not the guard.
  - A regression test should assert the outcome, not the lock observation.

## V4 — Readiness register (2026-10-25)

- `docs/verification/post-phase6/README.md` holds the fresh verification
  summary and the register R1–R10, each with type (verified defect, risk,
  open decision or observation), severity, evidence, action and whether it
  blocks Phase 7.
- **Blocking Phase 7:**
  - R4: no approved real judgment source;
  - R5: the brief's gate (owner-agreed thresholds on Phase 4 and 5
    evaluations) cannot be met, because both evaluations are synthetic
    engineering checks and no thresholds are agreed;
  - R6: the D1 privacy review, for any real case.
- **Not blocking:**
  - R1: race regression test;
  - R2: notes unencrypted at rest (local only);
  - R3: retention of 8 dumps, 2 base backups and 3+ restore databases;
  - R7: real-model checks (recommended before Phase 7);
  - R8: the brief is not version-controlled;
  - R9: a cosmetic slip in the Phase 6 checkpoint;
  - R10: no signed-in use of review on `lexflow` yet.
- **Verified application defects found:** none.

## V5 — Phase 7 proposal (2026-10-25)

- `docs/PHASE7_PROPOSAL.md` is a draft for the owner, read against the brief
  (Phase 7 and the evaluation rule). It covers:
  - problem and users;
  - the gate and prerequisites;
  - what is in and out of scope;
  - safety gates S1–S6, proposed as absolute because they restate the
    brief's "done when";
  - quality metrics Q1–Q5, whose values are **left for the owner to set**
    after a baseline measurement;
  - data provenance;
  - evaluation method;
  - failure handling;
  - security and audit;
  - the decisions required (§10), acceptance criteria and milestones.
- Nothing was implemented, no model was called and no dataset was acquired.
- One claim was corrected while drafting: the current front-end contract
  has **no** `outcomeAssessment` field; only the original mock contract
  (brief §2) had one.

Checkpoint: V5 — post-Phase-6 review complete (docs/verification/post-phase6/checkpoint.json); next action: owner reviews README.md and docs/PHASE7_PROPOSAL.md and decides §10.

## V3 — Functional checks and the first-review race (2026-10-25; recorded late)

*An earlier attempt to append this section did not reach the file. This
section is therefore placed after V4 and V5. The "Correction" bullets at
the end of V2 belong to this section: they cover the race probe's 4th run.*

**No signed-in action on `lexflow`.** Every behaviour below is covered by an
automated test that **passed fresh in V1**, on the disposable `lexflow_test`
(backend) or `lexflow_e2e` (browser); no existing data was changed. All test
names below were confirmed to exist in `server/tests`.

| # | Behaviour | Tests (fresh in V1) |
|---|---|---|
| 1 | A finding starts unreviewed | `test_analysis_reviews.py::test_every_finding_starts_unreviewed`; `review.test.tsx` "marks every finding as unreviewed"; e2e |
| 2 | Accept, edit, reject and clear work as specified | `test_accept_edit_reject_and_clear_keep_a_complete_history`, `test_edit_rules`; `review.test.tsx` (accept, edit, reject and clear); e2e (accept and edit) |
| 3 | An edit keeps the AI's wording | the same test (`run.result == result()`); `test_review_isolation.py::test_reviewing_never_changes_the_evidence_recorded_for_the_run`; `review.test.tsx` "edits the wording, keeping the AI's original" |
| 4 | The history records reviewer and time | `test_accept_edit_reject_and_clear_keep_a_complete_history` (versions, actors); `review.test.tsx` (history entries) |
| 5 | Stale-source indicators | `review.test.tsx` "warns when a finding's source changed"; `test_case_brief.py` (changed and unchanged); `test_review_lifecycle.py` (re-extraction, deletion) |
| 6 | A paralegal cannot decide or read notes | `test_only_the_cases_advocates_and_administrators_decide` (403); `test_notes_are_private_to_reviewers`; `review.test.tsx` (no controls); e2e (paralegal) |
| 7 | Clients cannot reach the workflow | `test_only_the_cases_advocates_and_administrators_decide` and `test_case_brief.py::test_who_may_export` (403) |
| 8 | Review actions on the timeline, never in the AI's evidence | `test_review_actions_appear_on_the_matter_timeline_without_their_content`; `test_review_isolation.py` (4 tests, including what a real worker run sends and a control test) |
| 9 | The DOCX holds only accepted findings, edits in the lawyer's wording | `test_case_brief.py::test_the_brief_holds_only_accepted_findings`; e2e (download is a zip package) |
| 10 | Sources and caveats; no notes, internal ids or "approved" | `test_each_finding_keeps_its_citation_and_reviewer`, `test_the_brief_never_holds_notes_or_internal_ids`, `test_the_brief_holds_only_accepted_findings` (no "approved", disclaimer) |
| 11 | A failed or concurrent change does not overwrite | `test_a_stale_version_is_refused_and_a_retry_adds_nothing` (409); `test_review_lifecycle.py::test_a_failure_mid_write_leaves_no_partial_review`; **the race probe below** |
| 12 | A repeated request adds no history | `test_a_stale_version_is_refused_and_a_retry_adds_nothing` (1 event after the retries) |

**Two simultaneous first decisions (the gap named in the Phase 6 report):**

- **Probe:** `race-probe/test_first_review_race.py`. It is *not* part of the
  test suite and lives outside `server/tests`. It runs with the project's
  fixtures (`-p tests.conftest`) on `lexflow_test`, with real commits
  (`committed_engine`, truncated afterwards).
  1. Connection A records "accepted" and keeps its transaction open.
  2. Connection B, which also saw no review, records "rejected".
  3. A third connection waits for up to 20 seconds to see B blocked on a
     lock. Then A commits.
- **Result over 9 runs** (`race-probe/probe-output.log`):
  - In every run, B was refused with `IntegrityError: UniqueViolation`, and
    exactly one review (accepted, version 1) and one history entry remained.
  - In 8 runs B was seen blocked first. Run 4 failed only the earlier
    lock-observation assertion, as described in the correction at the end
    of V2.
  - The API maps `IntegrityError` to 409 `review-changed`
    (`api/reviews.py`).
- **First attempt:** with a 5-second window, the probe failed its own "B was
  blocked" check, because B had not reached its insert in time.
- **Conclusion:** the guard works, but the suite has no regression test for
  it (register R1). The recommended test asserts the outcome, not the lock
  observation. Adding it is a code change, so it is not made in this review.

Checkpoint: V5 — post-Phase-6 review complete (docs/verification/post-phase6/checkpoint.json); next action: owner reviews README.md and docs/PHASE7_PROPOSAL.md and decides §10.

- *Note, when preparing the commit:* `git diff --check` flagged the trailing
  spaces on two pytest `E` lines in `mutation-output.log`, and a blank last
  line. Only that whitespace was removed. No other characters changed.
  (The committed Phase 6 copy has the same whitespace.)
