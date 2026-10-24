"""Review decisions never become model input (Phase 6, AC3).

The analysis evidence (``evidence.assemble``) sends the case's most recent
timeline entries to the model. Review actions are shown on the matter
timeline but are derived from the review history, so neither the decisions,
the lawyer's wording, the notes nor the timeline labels may appear in the
evidence or the prompt of a later analysis. A review also never changes the
evidence recorded for the run it is about. SYNTHETIC data; the provider is a
scripted fake that records what it was sent."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from lexflow.analysis import evidence as evidence_mod
from lexflow.analysis import prompt, runs
from lexflow.config import Settings
from lexflow.models import AnalysisRun, Case, User
from tests.access_fixtures import SATTVIK
from tests.analysis_fakes import ScriptedAnswers
from tests.embedding_fakes import make_ready
from tests.review_fixtures import ready_run
from tests.test_analysis_runs import configure, start, work  # noqa: F401 - fixture and helpers

As = Callable[[str], TestClient]
NOTE = "SYNTHETIC-PRIVATE-REVIEW-NOTE-7731"
WORDING = "SYNTHETIC-LAWYER-WORDING-4419"
REASON = "SYNTHETIC-REJECTION-REASON-2287"
LEAKS = (NOTE, WORDING, REASON, "AI finding reviewed", "lawyer's wording", "rejected")


def review_everything(as_: As, run: AnalysisRun) -> None:
    lead = as_("lead")
    base = f"/api/cases/{SATTVIK}/analysis-runs/{run.id}/reviews"
    decisions: list[tuple[str, dict[str, Any]]] = [
        ("F1", {"status": "edited", "reviewedText": WORDING, "note": NOTE}),
        ("F2", {"status": "rejected", "note": REASON}),
        ("C1", {"status": "accepted", "note": NOTE}),
    ]
    for finding, body in decisions:
        response = lead.put(f"{base}/{finding}", json={**body, "expectedVersion": 0})
        assert response.status_code == 200, response.text


def evidence_now(db: Session, document: uuid.UUID) -> evidence_mod.Evidence:
    case = db.get(Case, SATTVIK)
    assert case is not None
    return evidence_mod.assemble(db, case, [document], runs.limits_from(Settings()))


def test_review_content_never_reaches_the_evidence_or_the_prompt(
    as_: As, db: Session, people: dict[str, User]
) -> None:
    document = make_ready(db, SATTVIK, "SYNTHETIC Notice.pdf", ["SYNTHETIC notice text."])
    before = evidence_now(db, document)
    run = ready_run(db, SATTVIK, requested_by=people["lead"].id)
    review_everything(as_, run)

    after = evidence_now(db, document)
    assert after.context.timeline == before.context.timeline  # the same timeline entries
    rendered = prompt.render(after)
    for leak in LEAKS:
        assert leak not in rendered, leak
        assert all(leak not in f"{e.label} {e.description}" for e in after.context.timeline)
    # The matter timeline does show the review actions (to staff).
    timeline = as_("lead").get(f"/api/cases/{SATTVIK}").json()["timeline"]
    assert sum(1 for e in timeline if e["kind"] == "review") == 3


def test_a_new_analysis_after_reviews_sends_no_review_content(
    as_: As,
    db: Session,
    people: dict[str, User],
    configure: Callable[..., Settings],  # noqa: F811 - the fixture imported from test_analysis_runs
) -> None:
    settings = configure()
    document = make_ready(db, SATTVIK, "SYNTHETIC Notice.pdf", ["SYNTHETIC notice text."])
    reviewed = ready_run(db, SATTVIK, requested_by=people["lead"].id)
    review_everything(as_, reviewed)

    started = start(as_("lead"), [document])
    assert started.status_code == 202, started.text
    provider = ScriptedAnswers(['{"facts": []}'])
    assert work(db, provider, settings)
    (request,) = provider.requests
    sent = f"{request.system_instruction}\n{request.prompt}"
    for leak in LEAKS:
        assert leak not in sent, leak


def test_reviewing_never_changes_the_evidence_recorded_for_the_run(
    as_: As, db: Session, people: dict[str, User]
) -> None:
    run = ready_run(db, SATTVIK, requested_by=people["lead"].id)
    recorded = (dict(run.evidence or {}), dict(run.result or {}), run.prompt_version)
    review_everything(as_, run)
    db.refresh(run)
    assert (run.evidence, run.result, run.prompt_version) == recorded
    shown = as_("lead").get(f"/api/cases/{SATTVIK}/analysis-runs/{run.id}").json()
    assert shown["result"]["facts"][0]["statement"] == recorded[1]["facts"][0]["statement"]


def test_control_an_ordinary_timeline_row_does_reach_the_prompt(
    db: Session, people: dict[str, User]
) -> None:
    """The channel the review design avoids is real: a ``timeline_events`` row
    is sent to the model. If review actions were stored as such rows, the
    tests above would fail."""
    from datetime import date

    from lexflow.models import TimelineEvent

    document = make_ready(db, SATTVIK, "SYNTHETIC Notice.pdf", ["SYNTHETIC notice text."])
    db.add(
        TimelineEvent(
            case_id=SATTVIK,
            event_date=date(2026, 10, 25),
            label="AI finding reviewed",
            description=f"SYNTHETIC control entry {NOTE}",
            actor_id=people["lead"].id,
        )
    )
    db.commit()
    assert NOTE in prompt.render(evidence_now(db, document))
