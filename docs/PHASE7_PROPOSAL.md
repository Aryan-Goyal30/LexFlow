# Phase 7 proposal — Outcome assessment (DRAFT, not approved)

Status: **proposal for the owner's review (2026-10-25). Nothing here is
approved.** *Note added later the same day:* the owner asked for the
workflow to be built as a **synthetic-only engineering demonstration**
(`docs/PHASE7_PLAN.md`, ADR 0021). The real-world gate below is unchanged and
still blocked.
- Phase 7 must not start until the decisions in §10 are made and the gate
  in §3 is met.
- Prepared after the post-Phase-6 review (`docs/verification/post-phase6/`).

## 1. What the brief asks (`docs/DEVELOPMENT_BRIEF.md`, Phase 7)

> Only start once Phase 4 and 5 evaluation results meet thresholds agreed with
> the project owner.
> Scope: an evidence-supported assessment that lists the precedents behind it,
> explains its reasoning, and states its limits. Behind a feature flag, off by
> default.
> Done when: the assessment never appears without supporting precedents; it is
> clearly labelled as decision support; it can be switched off.

The original front-end mock contract (brief §2) had an optional
`outcomeAssessment`. The Phase 5 contract, generated from the server's
OpenAPI, has none. Phases 5 and 6 deliberately discard any outcome content
the model returns: the output parser's `OUTCOME_KEYS` and the validator's
`outcome-wording` removals.

## 2. Problem and users

- **Problem:** after the lawyer has reviewed a case's AI findings (Phase 6),
  the advocate wants a structured, evidence-backed view of how comparable
  decided cases went, and why. That view must be grounded in real
  precedents, explain its reasoning, and state its uncertainty and limits.
  It is never a prediction presented as fact.
- **Users:** the lead advocate and associate advocates on a case, and the
  Administrator. Paralegals read only (to be decided, §10). Clients: never.

## 3. Gate and prerequisites (all required before implementation)

1. **Evaluation data exists** (register R5):
   - a lawyer-labelled retrieval set, as the brief asks for Phase 4 (10–20
     sample cases, each with the judgments a lawyer considers relevant);
   - a lawyer-labelled analysis set for Phase 5 (facts, issues and
     contradictions a lawyer confirms for those cases).
2. **Thresholds agreed** on those sets (§5), and the current system measured
   against them.
3. **A real, licensed judgment source** approved and imported with
   provenance (register R4). Synthetic judgments may be used for
   engineering tests only, never for an assessment shown as real.
4. **The privacy, confidentiality and provider-terms review (D1) is
   complete**, if any real case will be assessed (register R6).
5. **Real-model behaviour checked** on synthetic documents (register R7), if
   the assessment uses an external model; that needs approved paid calls.

Preparation for items 1, 3 and 4 (drafts, 2026-10-25):
- `docs/phase7-prerequisites/SOURCE_CANDIDATE_SCI_JUDGMENTS.md`;
- `docs/phase7-prerequisites/ANNOTATION_GUIDE.md`;
- `docs/phase7-prerequisites/PRIVACY_REVIEW_CHECKLIST.md`.

None of these is approved.

## 4. Scope

**In scope (proposed):**
- An `outcome-assessment` feature flag, off by default. The server reports it
  in the analysis setup, and the UI hides everything when it is off.
- An assessment produced only from:
  - the case's **lawyer-accepted** findings (Phase 6), never unreviewed or
    rejected ones;
  - **retrieved real judgments** with provenance.
- Each assessment holds:
  - the precedents relied on (each a retrieved judgment passage, with its
    citation from the collection);
  - for each precedent, how it supports or cuts against the client's
    position, with a verbatim quote;
  - the reasoning in steps that cite those precedents and accepted findings;
  - uncertainty stated as categories, not percentages (for example
    "precedents point one way / mixed / insufficient"; the categories are to
    be agreed);
  - limits (what was not considered, what is missing).
- Validation before display, as in Phase 5:
  - **no assessment without at least one verified supporting precedent**;
  - every cited precedent retrieved for this run and every quote verbatim;
  - invented citations removed;
  - an "insufficient basis" result instead of a guess.
- Lawyer review of the assessment, reusing the Phase 6 workflow. It goes
  into the case brief only once accepted, and labelled.
- Audit (`assessment.requested`, `.completed`, `.reviewed`; codes and counts
  only). The original assessment is kept and never overwritten.

**Out of scope:**
- Numerical win probabilities or percentages.
- Assessments of real client cases before D1.
- Any assessment based on synthetic judgments presented as real.
- Automatic advice to clients; client-portal visibility.
- Training or fine-tuning models.
- Local LLMs; new external services.
- Acquiring datasets without verified permission.

## 5. Quality and safety thresholds (PROPOSED; every value needs owner approval)

**Safety gates.** These follow directly from the brief's "done when" and are
proposed as absolute:

| # | Gate | Proposed requirement |
|---|---|---|
| S1 | An assessment is shown only with supporting precedents | 100% of displayed assessments cite at least 1 verified, retrieved precedent (enforced by validation and tested) |
| S2 | Grounding | 0 displayed citations not retrieved for the run; 0 quotes not found verbatim in their passage |
| S3 | Labelling | 100% of displays and exports carry the decision-support label |
| S4 | Off switch | with the flag off, no route, field or UI element exposes an assessment (tested) |
| S5 | No numerical outcome probability | 0 percentages or probabilities in displayed text (validation pattern plus tests) |
| S6 | Synthetic data | 0 assessments shown as real that rest on a synthetic judgment |

**Quality thresholds.** These need lawyer-labelled data. The values are
**not** proposed here and are left for the owner to set after a baseline
measurement:

| # | Metric (on the lawyer-labelled sets) | Value |
|---|---|---|
| Q1 | Retrieval recall@10 and precision@10 (brief, Phase 4) | to be agreed |
| Q2 | Share of assessment reasoning steps a reviewing lawyer marks "supported by the cited precedent" | to be agreed |
| Q3 | Share of assessments whose uncertainty category the reviewing lawyer agrees with | to be agreed |
| Q4 | Rate of "insufficient basis" when the labelled set says the evidence is insufficient | to be agreed |
| Q5 | Inter-reviewer agreement on Q2 and Q3, if two lawyers label (to know whether the metric is meaningful) | to be agreed |

**Suggested method for setting the values:** measure the system as built on
the labelled sets; have the owner and a lawyer review the misses; set each
threshold with a written rationale; record it in the Phase 7 plan before
implementation.

## 6. Data provenance and synthetic versus real data

- Real judgments: only from an approved source, with:
  - terms URL, verified reuse permission, who checked and when;
  - source URL per judgment;
  - de-duplication;
  - a separate source key.

  The importer already records most of this (Phase 4).
- The SYNTHETIC demo judgments (live) and the evaluation fixtures stay
  labelled. Remove the demo judgments (`remove --source`) before a real
  collection is relied on. Evaluation sets are never imported into the live
  collection.
- The lawyer-labelled sets are stored in the repository (the brief: "keep the
  evaluation set and results in the repo"), with labeller, date and the
  source of each judgment.

## 7. Evaluation method and test data

- **Offline harness**, extending `server/scripts/evaluate_analysis.py`:
  deterministic scenarios for S1–S6 (planted unsupported assessments,
  invented citations, percentages, synthetic precedents, flag off).
  Conformance only, like Phase 5.
- **Lawyer evaluation:** run on the labelled sets, with lawyers scoring Q2
  and Q3 against a written rubric. Results are recorded with commit,
  versions (prompt, schema, validator) and dataset hashes.
- **Real-model runs** only if approved (budget, synthetic documents first).

## 8. Failure handling, uncertainty and safeguards

- Insufficient precedents or evidence: show "insufficient basis", never a
  guess.
- Validation removes unsupported content and counts it, as in Phase 5. If
  nothing verifiable remains, nothing is shown.
- Model or provider errors use the Phase 5 run lifecycle: retries, stale
  versions, user-safe messages.
- Wording that states a legal conclusion as fact, or a probability, is
  removed. The patterns have known limits (Phase 5 M10), so the lawyer
  review is mandatory before any use.
- Every display and export carries the decision-support disclaimer.

## 9. Security, authorization, audit, privacy

- New action `run-assessment` / `review-assessment`, reusing `authz.py` (the
  holders are to be decided, §10). Archived cases are read-only; clients get
  no access.
- Audit holds codes and counts only, never reasoning text or notes.
- Model input only from accepted findings and retrieved judgments; never
  review notes or the timeline's review entries (the Phase 6 isolation
  tests are extended).
- Real client material only after D1. Encryption-at-rest decision (register
  R2) before any non-local use.

## 10. Decisions required before implementation

1. Approve the gate in §3, and who builds and labels the evaluation sets.
2. Set the quality threshold values Q1–Q5, or decide that some are not
   used.
3. Approve the real judgment source (R4), or confirm Phase 7 runs on
   synthetic data for engineering only (in which case nothing may be shown
   as a real assessment).
4. Decide D1 for any real case (R6).
5. Approve real-model calls and a budget (R7), or choose not to use a model
   for the assessment.
6. Decide who may run, review and read assessments (paralegals?).
7. Choose the uncertainty categories and their wording.
8. Decide whether an accepted assessment may enter the case brief, and with
   which label.

## 11. Acceptance criteria and tests (proposed)

| # | Criterion | Tests |
|---|---|---|
| A1 | Flag off by default; off means invisible everywhere | API, UI and e2e tests with the flag off |
| A2 | Never without supporting precedents (S1) | validation unit tests; offline scenarios; mutation check |
| A3 | Grounding (S2) and no probabilities (S5) | validation tests; offline scenarios |
| A4 | Labelled as decision support (S3) | UI and export tests |
| A5 | Only accepted findings and real, retrieved precedents as input; review content never sent to the model | evidence-isolation tests (extending Phase 6) |
| A6 | Access, audit and archive rules | API tests per role |
| A7 | Lawyer review of the assessment; the original is kept | API and UI tests (reusing the Phase 6 patterns) |
| A8 | Quality thresholds met on the labelled sets | evaluation report in `docs/verification/phase7/` |
| A9 | Fresh full verification (pytest, `npm run check`, Playwright, mutation) | logs in `docs/verification/phase7/` |
| A10 | Records agree (plan, ADR, SRS, traceability, log, checkpoint); one closure commit | review at closure |

## 12. Milestones (proposed)

| M | Deliverable | Evidence |
|---|---|---|
| M0 | Decisions in §10 recorded; Phase 7 plan written from this proposal | plan, decision log |
| M1 | Lawyer-labelled evaluation sets and a baseline measurement | dataset files plus report |
| M2 | Feature flag; contract and schema for the assessment (additive migration) | migration and flag tests |
| M3 | Assessment generation behind the provider interface; validation (S1–S6) | unit tests and offline scenarios |
| M4 | Review workflow for assessments; brief integration (if approved) | API, UI and e2e tests |
| M5 | Evaluation against Q1–Q5 | evaluation report |
| M6 | Full verification, records, closure commit | verification logs |
