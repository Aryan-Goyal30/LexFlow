# Phase 7 plan: outcome assessment as a synthetic-only engineering demo

Status: **the synthetic-only engineering demonstration is implemented and
verified (2026-10-25); the real-world Phase 7 gate is BLOCKED.**
- Authorised by the owner's "overnight master execution" instruction, which
  asks for a clearly labelled, synthetic-data-only engineering demonstration
  of the outcome-assessment workflow.
- This plan is derived from `docs/PHASE7_PROPOSAL.md`, which stays a
  proposal.
- **The real-world Phase 7 gate stays BLOCKED** (register R4, R5, R5a, R6 in
  `docs/verification/post-phase6/README.md`):
  - no approved judgment source;
  - no lawyer-labelled evaluation sets or agreed thresholds;
  - no privacy sign-off;
  - real-model behaviour unverified.
- Nothing built here claims legal accuracy.

Record of the work: `docs/verification/overnight-completion/execution-log.md`
and `checkpoint.json`. Verification evidence: `docs/verification/phase7/`.

## 1. Brief (Phase 7) and how the demo meets it

> Scope: an evidence-supported assessment that lists the precedents behind
> it, explains its reasoning, and states its limits. Behind a feature flag,
> off by default. Done when: the assessment never appears without
> supporting precedents; it is clearly labelled as decision support; it can
> be switched off.

The demo implements this end to end. It uses only synthetic judgments and a
scripted (non-AI) provider. Section 2 records each decision; the reasons and
alternatives are in ADR 0021.

## 2. Design decisions (D7-1 to D7-10)

### D7-1 Feature flag

- `LEXFLOW_OUTCOME_ASSESSMENT` (default `false`). Settings refuse `true`
  unless `LEXFLOW_ENV` is `test` or `development` **and** the database is a
  test or e2e database, the rule the scripted provider already follows. The
  flag therefore cannot be switched on against the live `lexflow`.
- The effective flag is the setting **and** migration 0013 being applied.
- **When off:**
  - every assessment route answers 404 "not found", exactly like an unknown
    route;
  - the analysis setup reports `assessmentEnabled: false`;
  - the case brief contains no assessment section;
  - the UI shows nothing about assessments.

### D7-2 Provider

- Assessments use a provider interface of their own, shaped like Phase 5's:
  name, model, `generate(request)`.
- Only the **scripted assessment provider** (deterministic; every sentence
  marked "[Scripted]") can be built.
- With `LEXFLOW_AI_PROVIDER=gemini`, assessment is unavailable: "a real
  model needs the owner's approval (R7)". **There is no Gemini code path for
  assessments**, so no paid call is possible.

### D7-3 Inputs and the evidence gate

- An assessment needs a ready analysis run of the same case and:
  - at least one **accepted or edited** fact, issue or contradiction;
  - at least one **accepted or edited** precedent comparison whose judgment
    passage still exists with the same text (the SHA-256 recorded with the
    run).
- **Excluded from the model input:**
  - unreviewed and rejected findings;
  - reviewers' notes, history and the timeline;
  - the case description and timeline;
  - anything not retrieved for the run.
- Edited findings are sent in the lawyer's accepted wording.
- If the gate fails, an `insufficient` assessment is stored with the reason
  and the provider is **not called**.
- The case must be a sample case unless `LEXFLOW_AI_ALLOW_CLIENT_DATA` (D1).

### D7-4 Contract

The model answers JSON:
- a summary;
- the precedents relied on, each with:
  - the finding id (`P1` …);
  - a stance: `supports`, `cuts_against` or `does_not_resolve`;
  - a verbatim quote from the judgment passage;
  - an explanation;
- reasoning steps, each citing accepted finding ids and/or cited precedents;
- an uncertainty category: `insufficient_basis`, `mixed_evidence`,
  `limited_support` or `evidence_supports_position`;
- missing evidence;
- limitations.

There are **no numbers and no probabilities**. The stored result adds the
following from the server, never from the model:
- the judgment metadata and the synthetic flag;
- the decision-support label;
- whether the result is demo-only;
- the versions.

### D7-5 Validation (`assessment-grounding-1`), strict

- Precedent references must be accepted precedents of this run. Quotes must
  occur verbatim in that passage, after normalisation, using Phase 5's quote
  rules.
- A reasoning step needs at least one reference. Every reference must be an
  accepted finding or a kept precedent; otherwise the step is removed.
- **Prose** (summary, explanations, steps, limitations) is rejected if it
  contains:
  - percentages, probabilities, odds or chances;
  - definitive outcome claims (Phase 5's outcome patterns, plus "will
    certainly", "guaranteed", "bound to");
  - invented citations or case names;
  - for synthetic precedents, wording that presents them as real or binding.
- **A rejected summary withholds the whole assessment** (`insufficient`).
- The uncertainty category must match the kept stances; otherwise it is
  lowered to a consistent one and counted.
- With no kept precedent or no kept reasoning step, the result is
  `insufficient`.
- Each removal is counted by reason code; no text is logged.

### D7-6 Persistence (migration 0013, additive)

- `outcome_assessments`: immutable once written. Status `ready`,
  `insufficient` or `failed`, plus the reason, provider, model, versions,
  input record (finding ids, review versions, passage hashes), result,
  removals and created time.
- `outcome_assessment_reviews`: the current decision. Unique per assessment,
  with a version.
- `outcome_assessment_review_events`: append-only history, unique on
  (review, version).
- Statuses and the concurrency rule are those of Phase 6: `expectedVersion`
  gives 409 when stale, and a repeated request adds nothing. "Edited" means
  the lawyer's wording for the summary; the original stays.

### D7-7 Generation lifecycle

- Generation is **synchronous in the request**, so there is no worker
  change. The scripted provider is local and instant, and the real-model
  path does not exist (D7-2).
- A provider error, or an unreadable answer twice in a row, stores a
  `failed` assessment with a safe reason code. Recovery is to generate
  again.
- Each generation is a new row; history is kept, newest first.
- The hourly per-user limit (`LEXFLOW_AI_RUNS_PER_USER_PER_HOUR`) applies.

### D7-8 Access and audit

- **Who:**
  - Generate and review: Administrator, lead and associate advocates
    (`run-assessment`, `review-assessment`), not on archived cases.
  - Read: staff on the case. Paralegals read without notes, as in Phase 6.
  - Clients: no access (staff router).
- **Errors:** a run of another case gives 404; an assessment of another run
  gives 404.
- **Audit:** `assessment.requested`, `assessment.completed`,
  `assessment.failed` and `assessment.reviewed`, with codes and counts only.
  The brief-export audit adds `assessmentIncluded`.

### D7-9 Brief

When the flag is on and the run has an **accepted or edited** ready
assessment, the newest such assessment appears in a separate section,
"Outcome assessment (decision support)". It includes:
- the lawyer's wording if edited;
- the uncertainty category in words;
- the cited precedents with quotes and stances;
- the reasoning;
- the limitations and missing evidence;
- the SYNTHETIC/demo label where it applies;
- the reviewer and date.

It is never mixed into the findings. An unreviewed or rejected assessment is
never exported.

### D7-10 UI

A card, "Outcome assessment (decision support)", appears on the AI Analysis
tab below a ready run, and only when `assessmentEnabled`. It shows:
- the prerequisites;
- a generate button (for those allowed);
- each state: loading, error, insufficient, failed, ready;
- the label, the demo banner and the uncertainty category;
- the precedents, with links to the judgment text;
- the reasoning steps, with links to the findings;
- the limitations;
- the review controls (the Phase 6 pattern) and the history.

## 3. Acceptance criteria (synthetic engineering demo)

All criteria were "not implemented" when this plan was written. Status at
closure, with the evidence (all in `docs/verification/phase7/` unless
noted):

| # | Criterion | Status | Evidence |
|---|---|---|---|
| P7-A1 | Flag off by default; off means no assessment exposed | **Implemented and verified** | `test_off_by_default_every_route_is_not_found_and_setup_says_so`, `test_with_the_flag_off_an_existing_assessment_never_reaches_the_brief`, `test_the_flag_is_refused_outside_a_test_or_e2e_database`; Vitest "shows nothing and asks nothing while the flag is off"; mutations P7-15, P7-20, P7-21, U7-1 |
| P7-A2 | No assessment without a verified retrieved precedent | **Implemented and verified** | gate tests and `test_no_verified_precedent_means_no_assessment`; harness scenarios; mutations P7-1, P7-8, P7-13, P7-14 |
| P7-A3 | Citations and quotes validated against the run's evidence | **Implemented and verified** | 51 adversarial tests in `test_assessment_validation.py`; harness; mutations P7-2 to P7-7, P7-9, P7-11 |
| P7-A4 | UI and export label decision support and synthetic evidence | **Implemented and verified** | `test_only_an_accepted_assessment_reaches_the_brief_in_its_own_labelled_section` (DOCX opened); Vitest; e2e demo journey; mutations P7-10, U7-2 |
| P7-A5 | Only accepted findings and retrieved evidence as input; notes and excluded findings never | **Implemented and verified** | `test_only_accepted_findings_reach_the_provider_never_notes_or_excluded_ones`, `test_a_changed_judgment_passage_cannot_support_an_assessment`; mutation P7-12 |
| P7-A6 | Authorization, audit and archive rules tested | **Implemented and verified** | `test_who_may_generate_read_and_review`, `test_notes_are_private_to_reviewers`, `test_an_archived_case_can_be_read_but_not_assessed_or_reviewed`, `test_runs_and_assessments_must_belong_together`, `test_assessments_are_audited_with_codes_and_counts_only`; e2e; mutations P7-18, P7-22 |
| P7-A7 | Review keeps the original; accept, edit, reject, clear | **Implemented and verified** | `test_review_keeps_the_original_and_follows_the_phase6_rules`, `test_assessment_review_race.py`; Vitest; mutations P7-16, P7-17, P7-19, U7-3 |
| P7-A8 | Offline harness covers the adversarial scenarios and records results | **Implemented and verified** | `scripts/evaluate_assessment.py`: 24 of 24 as expected (`assessment-eval-2026-10-25.md`); `test_assessment_evaluation.py` |
| P7-A9 | Full backend, frontend and e2e verification recorded | **Implemented and verified** | `pytest-full.log`, `static-checks.log`, `npm-check.log`, `playwright.log`, `mutation-report.md`, `phase6-mutation-recheck/` |
| P7-A10 | Plan, ADR, SRS, traceability, log and checkpoint agree | **Implemented** (checked at closure) | this plan, ADR 0021, SRS FR-20/20a, TRACEABILITY, `docs/verification/overnight-completion/` |
| Real-world gate | Approved source (R4), lawyer-labelled sets and agreed thresholds (R5, R5a), privacy sign-off (R6), real-model checks (R7) | **Blocked by missing external evidence or approval** | `docs/verification/post-phase6/README.md`; not applicable to the synthetic demo |

## 4. Milestones

| M | Deliverable |
|---|---|
| B1 | Domain values, models, migration 0013, the flag, actions; model and migration tests |
| B2 | Assessment package (inputs, prompt, output, validation, scripted provider, service); adversarial unit tests |
| B3 | API, audit, brief section; API tests (roles, flag off and on, states) |
| B4 | UI (types, service, hooks, card, review); Vitest |
| B5 | e2e (flag on in the e2e app); offline evaluation harness; mutation checks |
| B6 | Full verification; ADR 0021, SRS, traceability, architecture, demo guide; final report |

## 5. Out of scope

- Real judgments.
- Real-model assessments.
- Numerical scores.
- Client-portal visibility.
- Assessment entries on the matter timeline (Phase 6 finding reviews stay
  there).
- Evaluation of legal quality.

## 6. How to resume

The newest record of this work is
`docs/verification/overnight-completion/checkpoint.json` (its `next_action`)
and the end of `docs/verification/overnight-completion/execution-log.md`.
Real-world Phase 7 work starts only after the owner settles R4, R5, R5a, R6 and
R7. It would then need a worker-based generation path for a real model and a
fresh evaluation.
