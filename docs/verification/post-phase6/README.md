# Post-Phase-6 verification and readiness register

Review of the state after the Phase 6 closure (`eada4ef`, parent `5302e41`),
carried out on 2026-10-25.
- Record of the work: `execution-log.md` (append-only, V0–V5).
- Machine-readable state: `checkpoint.json`.
- Phase 7 proposal (not approved): `docs/PHASE7_PROPOSAL.md`.

This review changed no application code, test, configuration, migration or
record.

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
| R1 | No regression test for two simultaneous *first* decisions on one finding | Risk (coverage gap; the guard itself works) | Low | The probe: 9 of 9 runs refused the second decision (unique index, then 409); one run failed only the probe's timing observation | Add the probe as `server/tests/test_review_race.py`, asserting the outcome (second decision refused; one review and one history entry), not the lock observation | No |
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

## Resume

> Resume the LexFlow post-Phase-6 review from `docs/verification/post-phase6/checkpoint.json`. Read its `next_action`, check Git state and the protected-file hash, and continue without repeating completed checks.
