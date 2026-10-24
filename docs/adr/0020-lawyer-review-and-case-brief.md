# 0020 — Lawyer review of AI findings and the case brief

Status: Accepted (Phase 6, 2026-10-25)

## Context

The brief's Phase 6 asks for:
- accept, reject or edit each AI finding, with an optional note;
- review actions recorded on the matter timeline;
- a case brief (PDF or DOCX) containing only accepted findings, with
  citations.

It is done when unreviewed findings are visibly marked and the export
contains only accepted findings.

Phase 5 stores each run's validated result as the record of what the model
said, with provenance (evidence ids, chunk ids, hashes, versions). The
matter timeline is shown to the staff on a case, and its 30 most recent rows
are sent to the model as background for every new analysis.

## Decision

- **Reviews live beside the result, never in it.**
  - `analysis_finding_reviews` holds the current decision per finding (run
    plus id, because ids are unique only within a run).
  - `analysis_finding_review_events` is the append-only history.
  - Both come from migration 0012, which is additive.
  - The run's `result` is never changed. An edit is the lawyer's wording,
    stored with the decision; the model's wording stays the record and stays
    on screen.
- **States and transitions:** `unreviewed`, `accepted`, `edited` (accepted
  with lawyer wording, which must differ from the AI's) and `rejected`.
  Clearing returns a finding to `unreviewed`; the history keeps every change
  with its actor and time.
- **Concurrency without locks across requests.** Each change sends the
  version it saw: a stale version gives 409, and a request that changes
  nothing adds no history entry. Database constraints keep the rows
  consistent:
  - one review per (run, finding id) and one history entry per (review,
    version);
  - the kind must match the id prefix;
  - wording exactly when the status is `edited`;
  - length limits.
- **Who:** a new action `review-analysis` with the same holders as
  `run-analysis` (Administrator, the lead advocate, associate advocates);
  never on archived cases. Paralegals see decisions and history but not the
  notes; clients never reach the routes.
- **The timeline without the privacy leak.**
  - Review actions are shown on the matter timeline as entries **derived
    from the review history** at read time, never as `timeline_events`
    rows. The evidence builder reads only `timeline_events`, so a decision,
    a note or lawyer wording can never become model input.
  - A test proves it: a control test shows that a `timeline_events` row
    does reach the prompt.
  - Timeline entries and audit details name the finding and the decision,
    never the wording or the note.
- **The brief:**
  - a DOCX made locally with `python-docx` (already a dependency);
    generated on request, not stored, no model call;
  - only accepted and edited findings (edited ones in the lawyer's wording,
    marked), each with its stored citation and its reviewer and date;
  - the number of unreviewed and rejected findings left out; never
    "approved" as a whole;
  - synthetic judgments labelled as fictional; sources that changed after
    the run flagged, never replaced;
  - the decision-support disclaimer; no notes and no internal ids.
  - Anyone who may view the analysis may export it. It needs at least one
    accepted finding. Each export is audited with counts only.
- **Without migration 0012** the review routes answer 503 and nothing else
  changes, as Phase 5 did without 0011.

## Alternatives considered

- *Store decisions inside `analysis_runs.result`:* rejected. It overwrites
  the model's record and makes history and concurrency hard.
- *Write review actions as `timeline_events` rows:* rejected. Those rows are
  model input (Phase 5 evidence), so notes and decisions would be sent to
  the provider. Filtering them out of the evidence by a marker would need a
  new column on an existing table, and one missed filter would leak.
- *PDF export:* not needed (the brief allows DOCX) and would add a
  dependency.
- *Require every finding to be reviewed before export:* not required by the
  brief. A partial brief contains only accepted findings and says how much
  is still unreviewed.

## Consequences

- The brief shows exactly what a lawyer accepted. Its quality is that of
  the review; the disclaimer says so.
- Notes are private to reviewers but stored in the database, which is
  local-only (ADR 0005).
- Migration 0012 was applied to the local `lexflow` database on 2026-10-25
  after a verified backup (Phase 6 log B8a).
- Precedent similarities and differences are shown as stated by the AI. Only
  the summary can be replaced by the lawyer's wording; the brief labels the
  points "as stated by the AI".
