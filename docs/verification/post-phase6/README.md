# Post-Phase-6 verification and readiness register

Review of the state after the Phase 6 closure (`eada4ef`, parent `5302e41`),
carried out on 2026-10-25.
- Record of the work: `execution-log.md` (append-only, V0–V5).
- Machine-readable state: `checkpoint.json`.
- Phase 7 proposal (not approved): `docs/PHASE7_PROPOSAL.md`.

This review changed no application code, test, configuration, migration or
record.
The follow-up (section "Follow-up" below) added one regression test and
planning documents; it changed no application code, configuration,
migration or record.

## Verified (fresh runs, 2026-10-25, HEAD `eada4ef`)

| Check | Result | Evidence |
|---|---|---|
| Backend tests | 1028 passed, exit 0 | `pytest-full.log` |
| ruff check and format, mypy (Windows and Linux), OpenAPI drift, `alembic check` (test database) | all exit 0 | `static-checks.log` |
| `npm run check` (lint, format, types, API types, 193 tests, build) | exit 0 | `npm-check.log` |
| Playwright (42, including review and export) | exit 0 | `playwright.log` |
| Phase 6 mutation checks (output written here, not over the Phase 6 report) | 19 of 19 caught | `mutation-report.md`, `mutation-output.log` |
| Two simultaneous first decisions (probe outside the suite) | in 9 of 9 runs the second decision was refused and one review remained (one run failed only the probe's timing observation; see the log, V3) | `race-probe/` |
| Live `lexflow` | at 0012 (head); data identical to the pre-migration state apart from the two new, empty tables; the API starts; `/api/health` OK; review routes refuse anonymous callers (401) | log, V2 |

These match every result recorded at the Phase 6 closure.

## Readiness register

Severity is the impact if the item is left as it is. **Blocks Phase 7** means
Phase 7 should not start (or cannot be evaluated) until the item is settled.

| # | Item | Type | Severity | Evidence | Recommended action | Blocks Phase 7 |
|---|---|---|---|---|---|---|
| R1 | No regression test for two simultaneous *first* decisions on one finding | Risk (coverage gap; the guard itself works) | Low | The probe: 9 of 9 runs refused the second decision (unique index, then 409); one run failed only the probe's timing observation | **Resolved in the follow-up:** `server/tests/test_review_race.py` (see below) | No |
| R2 | Reviewers' private notes are stored unencrypted in PostgreSQL | Accepted limitation (ADR 0020; local-only deployment, ADR 0005) | Medium if the database is ever copied or exposed; low on one local machine | `analysis_finding_reviews.note`, `analysis_finding_review_events.note` | Owner decision before any non-local deployment, or before real client material is used: encryption at rest (disk or column level), or no notes | Only if Phase 7 uses real client material |
| R3 | Copies of live data outside `lexflow`: 8 dumps and 2 base backups in `server/var/backups/` (git-ignored; from Phase 2 to the 0012 migration); the databases `lexflow_pre0012_verify`, `lexflow_p3_restore`, `lexflow_restore_check`; the M8 scratch-server restore | Open decision (retention) | Low (sample and synthetic data today); rises once real data exists | log V2; Phase 5 log M8c | The owner decides how long each is kept. Nothing was deleted here | No |
| R4 | No real judgment source is approved; the live collection holds only 3 SYNTHETIC demo judgments | Open decision | High for Phase 7: an outcome assessment "lists the precedents behind it", and synthetic precedents cannot support real conclusions | Phase 5 log M10.3; SRS §5 | Approve a source only with: authoritative publisher, terms URL, verified reuse permission (who and when), provenance per judgment, de-duplication, and separation from synthetic and evaluation data | **Yes** |
| R5 | The brief's Phase 7 gate cannot be met: "only start once Phase 4 and 5 evaluation results meet thresholds agreed with the project owner". No thresholds are agreed, and both evaluations are synthetic engineering checks (Phase 4: "legal research quality is unevaluated"; Phase 5: conformance to synthetic scenarios) | Open decision, plus an unmet prerequisite | High | brief, Phase 7; `docs/verification/phase4/judgment-eval.md`; `docs/verification/phase5/analysis-eval-2026-10-25.md` | Build the lawyer-labelled evaluation sets the brief describes (10–20 sample cases with relevant judgments), measure, then agree thresholds. Proposed metrics: `docs/PHASE7_PROPOSAL.md` | **Yes** |
| R6 | AI analysis is limited to sample (fictional) cases until a privacy, confidentiality and provider-terms review (decision D1) | Open decision | High for any real use | `LEXFLOW_AI_ALLOW_CLIENT_DATA=false`; Phase 5 plan §9 | Complete the review before any real case is analysed or assessed | **Yes**, for real cases (not for a synthetic-only Phase 7) |
| R7 | The real model's behaviour under prompt `case-analysis-v2` is unverified: contradiction reporting on the planted 2015/2017 document, live rejection of injected output, the cause of the M8e HTTP 400s | Open decision (needs paid or real calls) | Medium | Phase 5 log M10.1–M10.2 | The owner decides whether to approve a small, budgeted set of real calls on synthetic documents | Not formally; recommended before Phase 7 relies on model quality |
| R8 | `docs/DEVELOPMENT_BRIEF.md` is not under version control (excluded in the local `.git/info/exclude`); its integrity rests on the recorded SHA-256 | Observation | Low | `git check-ignore -v` | The owner decides whether to track it (tracking it would not change its bytes). Not changed here | No |
| R9 | The Phase 6 checkpoint's AC4 note says "review.test.tsx 9 passed"; the file ended with 13 tests (the total of 193 is right) | Verified cosmetic inaccuracy in a record | Very low | `docs/verification/phase6/checkpoint.json` | Leave the historical record; this register notes it | No |
| R10 | No signed-in review has yet been made on `lexflow` (the review tables have 0 rows); runtime behaviour is verified on disposable databases only | Observation | Low | log V2 | The owner tries one review and one export in the local app on the sample case | No |

**Verified defects found in this review:** none in the application. R9 is
a slip in a record.

## Follow-up (2026-10-25): regression test and Phase 7 prerequisites

Authorised by the owner's "safe next steps" instruction. Record of the
work: `execution-log.md`, sections F0–F5. Evidence: `followup/`. Phase 7
remains **blocked**.

**R1, resolved:** `server/tests/test_review_race.py`.
- It runs on `lexflow_test` with real commits, through the real API.
- The test waits until the database shows the second request blocked behind
  the first decision, then commits the first. The order is fixed, not left
  to timing.
- It asserts:
  - 409 `review-changed` for the second request;
  - exactly one review (accepted, version 1, no note);
  - exactly one history entry;
  - no `analysis.finding_reviewed` audit event for the refused request.
- **Results:**
  - 10 of 10 runs passed (`followup/review-race-runs.log`);
  - a mutation check (conflict mapping removed) was caught, 500 instead of
    409, and the file was restored byte for byte;
  - the full suite: 1029 passed (`followup/pytest-full.log`);
  - ruff, mypy (Windows and Linux) and the OpenAPI check all exit 0
    (`followup/static-checks.log`).
- **Likely cause of the probe's earlier timing miss:** PostgreSQL keeps
  one activity snapshot per transaction. The probe polled inside one
  transaction, so it could keep reading a stale snapshot. The test polls in
  a fresh transaction each time.

### Decision register: Phase 7 prerequisites

| # | Decision | Recommendation | Evidence | Unresolved questions | Depends on | Approval gate |
|---|---|---|---|---|---|---|
| R4 | Real judgment source | Keep the Indian Supreme Court Judgments open dataset (AWS registry, CC-BY-4.0 stated) as the **leading candidate**; do not approve yet. If approved, pilot one practice area with a few hundred judgments, fetched by the owner. LexFlow does not crawl | `docs/phase7-prerequisites/SOURCE_CANDIDATE_SCI_JUDGMENTS.md` §1–2 (registry, README, licence file read 2026-10-25) | What the CC BY grant covers, and who the licensor is; the upstream portal's terms (not read: sci.gov.in returned 403); court-ordered prohibitions; personal data in judgments; commercial use; fidelity of the text and citations; the form of attribution | A lawyer's review of the terms; the practice area (Phase 4 Gate 2) | Owner records the source in `judgment_sources` form: terms URL, date, reader, permitted use |
| R5 | Lawyer-labelled evaluation sets | Recruit one qualified reviewer (two if possible, for agreement). Pilot 2 query cases, then 10–20, built from public judgments with a time cut-off (no client data) | `docs/phase7-prerequisites/ANNOTATION_GUIDE.md`; existing sets are SYNTHETIC (`docs/verification/phase4/judgment-eval.md`) | Who the reviewer is and their time and cost; the area; whether a second reviewer is available | R4 (an approved source for candidates); a separate evaluation database | Owner approves the guide and the reviewer; the sets are committed with provenance |
| R5a | Quality thresholds | Set **after** a baseline on the lawyer-labelled sets, with written reasons. Proposed form: a minimum per metric (for example no worse than keyword search alone) plus failures unacceptable at any rate. **No values proposed** | `ANNOTATION_GUIDE.md` §9; `docs/PHASE7_PROPOSAL.md` §5 (draft) | All values | R5 | Owner records the values in the Phase 7 plan before implementation |
| R6 | D1 privacy review | Complete the checklist before any real case is stored for AI use, sent to Gemini, or used in evaluation. Until then, sample and synthetic cases only | `docs/phase7-prerequisites/PRIVACY_REVIEW_CHECKLIST.md`; Phase 5 plan §9 | The applicable law and its commencement; the provider's terms; consent; cross-border transfer; retention; redaction; encryption (R2) | A lawyer or privacy reviewer; the provider's current terms | Owner sign-off (checklist H) before `LEXFLOW_AI_ALLOW_CLIENT_DATA=true` |
| R7 | Real-model checks | Unchanged: a small, budgeted set of real calls on synthetic documents, if the owner approves | Phase 5 log M10 | Budget; model choice | Owner | Owner approves the calls and the budget |

**Phase 7 gate (unchanged):** R4, R5 and R5a are all required. R6 is also
required for any real case. Then the decisions in `docs/PHASE7_PROPOSAL.md`
§10.

## Resume

> Resume the LexFlow post-Phase-6 review from `docs/verification/post-phase6/checkpoint.json`. Read its `next_action`, check Git state and the protected-file hash, and continue without repeating completed checks.
