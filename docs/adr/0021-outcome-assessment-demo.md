# 0021 — Outcome assessment as a synthetic-only engineering demonstration

Status: Accepted for the demonstration (Phase 7, 2026-10-25). **Real-world use
is blocked** until the external prerequisites below are met.

## Context

The brief's Phase 7 asks for an evidence-supported assessment that lists the
precedents behind it, explains its reasoning and states its limits, behind a
feature flag that is off by default. It is done when:
- the assessment never appears without supporting precedents;
- it is clearly labelled as decision support;
- it can be switched off.

The brief also says to "only start once Phase 4 and 5 evaluation results meet
thresholds agreed with the project owner". That gate cannot be met today
(`docs/verification/post-phase6/README.md`):
- R4: no approved real judgment source; only SYNTHETIC judgments exist;
- R5, R5a: the evaluations are synthetic engineering checks; there are no
  lawyer-labelled sets and no agreed thresholds;
- R6: no privacy sign-off for real client material;
- R7: real-model behaviour is unverified.

For the college submission, the owner asked for the complete workflow to be
built and verified on synthetic data, honestly labelled, without claiming
legal validity (`docs/PHASE7_PLAN.md`).

## Decision

- **Off by default, and impossible against the live database.**
  - `LEXFLOW_OUTCOME_ASSESSMENT` defaults to false.
  - The settings refuse it unless `LEXFLOW_ENV` is test or development and
    the database name has a "test" or "e2e" part (the scripted provider's
    rule).
  - The effective flag also needs migration 0013.
  - When it is off, every assessment route answers 404 exactly like an
    unknown route: a router dependency runs before the body is read. The
    setup reports `assessmentEnabled: false`, the brief has no assessment
    section, the export audit has no assessment key, and the UI renders and
    requests nothing.
- **No real-model path.** Assessments use their own provider seam, shaped
  like Phase 5's, but only the scripted (non-AI) provider can be built. With
  Gemini configured, assessment is unavailable ("needs the owner's
  approval"). No paid call is possible.
- **Inputs are what a lawyer accepted, and nothing else.**
  - Accepted or edited facts, issues and contradictions (edited ones in the
    lawyer's wording).
  - Accepted precedent comparisons, each with its judgment passage reloaded
    and compared with the content hash recorded with the run.
  - Never notes, review history, rejected or unreviewed findings, the case
    description or the timeline.
  - With no accepted finding or no unchanged accepted precedent, the result
    is `insufficient` and **no provider call** is made.
- **A contract without numbers.** The answer is JSON:
  - a summary;
  - cited precedents (id, stance, verbatim quote, explanation);
  - reasoning steps with references;
  - one of four uncertainty categories;
  - missing evidence and limitations.

  Unknown top-level keys (a "probability", a "synthetic": false) are
  discarded and counted. Labels such as decision support, synthetic and
  demo-only are set by the server.
- **Strict validation (`assessment-grounding-1`).**
  - Cited precedents must be accepted comparisons of the run, with quotes
    verified in the passage under Phase 5's rules.
  - Every reasoning reference must be an accepted finding or a kept
    precedent.
  - Probability, percentage, odds and chance wording, outcome predictions,
    definitive claims, invented citations and "real or binding" claims about
    synthetic judgments are rejected.
  - A rejected summary withholds the whole assessment.
  - The category must fit the kept stances (otherwise it is lowered, and
    caution is never overridden).
  - No kept precedent or no kept step gives `insufficient`.
- **Immutable assessment, separate review.**
  - Migration 0013 adds `outcome_assessments` (written once),
    `outcome_assessment_reviews` (current decision, unique per assessment,
    versioned) and `outcome_assessment_review_events` (append-only).
  - Review follows Phase 6: accept, edit (the lawyer's wording of the
    summary), reject or clear; 409 when stale; a repeated request adds
    nothing.
  - An assessment is not a lawyer's view until accepted.
- **Generation in the request.** The scripted provider is local and instant,
  so no queue is used. A real model would first need the worker's queue,
  lease and retries.
- **Access and audit** as in Phase 6:
  - generate and review: Administrator, lead and associate, not on archived
    cases;
  - read: staff on the case, without notes for paralegals;
  - clients: never;
  - audit: `assessment.requested`, `completed`, `failed` and `reviewed`,
    with codes and counts only.
- **Brief.** Only an accepted or edited ready assessment, the newest one,
  appears, in its own "Outcome assessment (decision support)" section with
  the demo label. It is never mixed into the findings.

## Consequences

- The whole workflow (gate, generation, validation, review, brief, UI) is
  demonstrable and tested on synthetic data:
  - adversarial unit tests;
  - API, race, Vitest and Playwright tests;
  - 24 offline scenarios;
  - 25 mutation checks.
- **The demo says nothing about legal quality.** Stances in the scripted
  output are assigned by position, not by reading the law. Every screen and
  the brief say so.
- The prose patterns are deliberately simple. They remove the clear cases
  and can miss paraphrases or catch an unusual sentence, so the lawyer's
  review stays mandatory.
- **Real use needs, in order:**
  1. an approved judgment source;
  2. lawyer-labelled evaluation sets with agreed thresholds;
  3. the D1 privacy sign-off;
  4. approved real-model checks;
  5. a worker-based generation path.

  None of these is claimed here.
- Timeline entries for assessment reviews are not added (findings' reviews
  are; see ADR 0020).
