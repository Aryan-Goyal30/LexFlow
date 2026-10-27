"""Generating, storing and reviewing outcome assessments (D7-3 to D7-7).

Generation runs in the request (D7-7): the only provider that can be built is
the local scripted one, so there is no network call to wait for. A real
model would need the worker's queue, lease and retries first (Phase 5); that
path is deliberately absent until the owner approves it (R7).

1. ``inputs.gather``: the accepted findings and unchanged precedent passages.
   If the gate fails, an ``insufficient`` assessment is stored and **no
   provider is called**.
2. The provider answers; an unreadable answer is asked for once more, then
   the assessment is ``failed`` (``invalid-output``). A provider error is
   ``failed`` with its safe code and message.
3. ``validation.validate`` keeps only what verifies; the verdict is stored.

An assessment row is never changed afterwards. Reviews follow Phase 6's rules
(``services.reviews``): versioned, append-only history, 409 when stale, a
repeated request adds nothing.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from lexflow.analysis.output import InvalidOutputError
from lexflow.analysis.provider import ProviderError
from lexflow.assessment import inputs as inputs_mod
from lexflow.assessment import output, prompt, validation
from lexflow.assessment.provider import AssessmentProvider, AssessmentRequest
from lexflow.models import (
    AnalysisRun,
    OutcomeAssessment,
    OutcomeAssessmentReview,
    OutcomeAssessmentReviewEvent,
)
from lexflow.services import reviews as finding_reviews

logger = logging.getLogger("lexflow.assessment")

MIGRATION_MISSING = (
    "Outcome assessment needs a database update (migration 0013) that is not applied yet."
)
PROVIDER_FAULT = "The assessment provider failed in an unexpected way. Try again later."
CHECK_FAULT = "LexFlow could not check the assessment, so nothing from it is shown."
MAX_OUTPUT_TOKENS = 8_192


def table_exists(session: Session) -> bool:
    """False before migration 0013: assessment is then unavailable, nothing fails."""
    return session.scalar(text("SELECT to_regclass('outcome_assessments')")) is not None


def pipeline_record() -> dict[str, str]:
    return {
        "promptVersion": prompt.PROMPT_VERSION,
        "schemaVersion": output.SCHEMA_VERSION,
        "schemaSha256": output.schema_sha256(),
        "validatorVersion": validation.VALIDATOR_VERSION,
    }


@dataclass(frozen=True)
class Generated:
    assessment: OutcomeAssessment
    called: bool


def created_since(session: Session, user_id: uuid.UUID, since: datetime) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(OutcomeAssessment)
            .where(
                OutcomeAssessment.requested_by_id == user_id, OutcomeAssessment.created_at >= since
            )
        )
        or 0
    )


def _row(
    run: AnalysisRun,
    provider: AssessmentProvider,
    *,
    requested_by: uuid.UUID,
    record: dict[str, Any],
    now: datetime,
) -> OutcomeAssessment:
    return OutcomeAssessment(
        run_id=run.id,
        case_id=run.case_id,
        requested_by_id=requested_by,
        provider=provider.name,
        model=provider.model,
        prompt_version=prompt.PROMPT_VERSION,
        inputs=record,
        created_at=now,
    )


@dataclass(frozen=True)
class Assessed:
    """The outcome of assessing one set of inputs (no database involved)."""

    status: str  # "ready", "insufficient" or "failed"
    reason_code: str | None
    reason: str | None
    result: dict[str, Any] | None
    removed: dict[str, Any] | None
    usage: dict[str, int]
    called: bool  # whether the provider was asked at all


def assess(
    provider: AssessmentProvider, gathered: inputs_mod.Inputs, *, allow_genuine: bool = False
) -> Assessed:
    """Gate, ask and validate. No database access: the API calls it for a run,
    and the offline evaluation (``scripts/evaluate_assessment.py``) for its
    SYNTHETIC scenarios, so both exercise the same code."""
    gate = gathered.gate(allow_genuine)
    if gate is not None:
        return Assessed("insufficient", gate, inputs_mod.GATE_REASONS[gate], None, None, {}, False)
    request = AssessmentRequest(
        system_instruction=prompt.SYSTEM_INSTRUCTION,
        prompt=prompt.render(gathered),
        response_schema=output.RESPONSE_SCHEMA,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        inputs=gathered,
    )
    usage: dict[str, int] = {}
    problem = InvalidOutputError("invalid-output", "The answer could not be read.")
    for _ in range(2):  # one more try for an unreadable or cut-off answer
        try:
            response = provider.generate(request)
        except ProviderError as error:
            return Assessed("failed", error.code, error.message, None, None, usage, True)
        except Exception as error:  # a provider bug must not fail the request
            # Only the type is logged: an exception's text could echo the request.
            logger.error("assessment: provider raised %s", type(error).__name__)
            return Assessed("failed", "provider-error", PROVIDER_FAULT, None, None, usage, True)
        for key, value in response.usage.items():
            usage[key] = usage.get(key, 0) + value
        if response.truncated:
            problem = InvalidOutputError("invalid-output", "The answer was cut off.")
            continue
        try:
            parsed = output.parse(response.text)
            verdict = validation.validate(parsed, gathered, scripted=provider.name == "scripted")
        except InvalidOutputError as error:
            problem = error
            continue
        except Exception as error:  # never store an answer that was not fully checked
            logger.error("assessment: checking the answer raised %s", type(error).__name__)
            return Assessed("failed", "validation-error", CHECK_FAULT, None, None, usage, True)
        return Assessed(
            verdict.status,
            verdict.reason_code,
            verdict.reason,
            verdict.result.model_dump(mode="json", by_alias=True) if verdict.result else None,
            verdict.removed.model_dump(mode="json", by_alias=True),
            usage,
            True,
        )
    message = f"The assessment could not be used twice in a row: {problem.message}"
    return Assessed("failed", "invalid-output", message, None, None, usage, True)


def generate(
    session: Session,
    run: AnalysisRun,
    provider: AssessmentProvider,
    *,
    requested_by: uuid.UUID,
    now: datetime,
    allow_genuine: bool = False,
) -> Generated:
    """Assess a ready run and store the outcome (flushes; the caller commits)."""
    gathered = inputs_mod.gather(session, run)
    record = {**gathered.record(), "pipeline": pipeline_record()}
    row = _row(run, provider, requested_by=requested_by, record=record, now=now)
    outcome = assess(provider, gathered, allow_genuine=allow_genuine)
    row.status, row.reason_code, row.reason = outcome.status, outcome.reason_code, outcome.reason
    row.result, row.removed, row.usage = outcome.result, outcome.removed, outcome.usage
    session.add(row)
    session.flush()
    return Generated(row, outcome.called)


def current_inputs(session: Session, run: AnalysisRun) -> dict[str, Any]:
    """The input record a new assessment of the run would use now."""
    return inputs_mod.gather(session, run).record()


def inputs_changed(assessment: OutcomeAssessment, current: dict[str, Any]) -> bool:
    """Whether the accepted findings (and their review versions), the precedent
    passages or the exclusions differ from what the assessment used."""
    stored = assessment.inputs or {}
    return any(
        stored.get(key) != current.get(key) for key in ("findings", "precedents", "excluded")
    )


# --- review (Phase 6 rules) ----------------------------------------------------------


class StaleVersionError(Exception):
    def __init__(self, current_version: int) -> None:
        super().__init__(current_version)
        self.current_version = current_version


@dataclass(frozen=True)
class Outcome:
    review: OutcomeAssessmentReview | None
    changed: bool
    wording_changed: bool = False
    note_changed: bool = False


def current_review(session: Session, assessment_id: uuid.UUID) -> OutcomeAssessmentReview | None:
    return session.scalar(
        select(OutcomeAssessmentReview).where(
            OutcomeAssessmentReview.assessment_id == assessment_id
        )
    )


def apply_review(
    session: Session,
    assessment: OutcomeAssessment,
    change: finding_reviews.Change,
    *,
    expected_version: int,
    actor_id: uuid.UUID,
    now: datetime,
) -> Outcome:
    """Record one decision (flushes, does not commit). Raises StaleVersionError."""
    review = session.scalars(
        select(OutcomeAssessmentReview)
        .where(OutcomeAssessmentReview.assessment_id == assessment.id)
        .with_for_update()
    ).one_or_none()
    version = review.version if review is not None else 0
    if expected_version != version:
        raise StaleVersionError(version)
    before = (
        finding_reviews.Change(review.status, review.reviewed_text, review.note)
        if review is not None
        else finding_reviews.Change("unreviewed", None, None)
    )
    if change == before:
        return Outcome(review, changed=False)
    if review is None:
        review = OutcomeAssessmentReview(
            assessment_id=assessment.id, case_id=assessment.case_id, version=0
        )
        session.add(review)
    review.status = change.status
    review.reviewed_text = change.reviewed_text
    review.note = change.note
    review.version = version + 1
    review.reviewed_by_id = actor_id
    review.reviewed_at = now
    session.flush()  # the unique assessment id refuses a concurrent first decision
    session.add(
        OutcomeAssessmentReviewEvent(
            review_id=review.id,
            assessment_id=assessment.id,
            case_id=assessment.case_id,
            status=change.status,
            reviewed_text=change.reviewed_text,
            note=change.note,
            version=review.version,
            actor_id=actor_id,
            occurred_at=now,
        )
    )
    session.flush()
    return Outcome(
        review,
        changed=True,
        wording_changed=change.reviewed_text != before.reviewed_text,
        note_changed=change.note != before.note,
    )


def history(session: Session, assessment_id: uuid.UUID) -> list[OutcomeAssessmentReviewEvent]:
    return list(
        session.scalars(
            select(OutcomeAssessmentReviewEvent)
            .where(OutcomeAssessmentReviewEvent.assessment_id == assessment_id)
            .order_by(OutcomeAssessmentReviewEvent.version)
        )
    )


def accepted_for_brief(
    session: Session, run_id: uuid.UUID
) -> tuple[OutcomeAssessment, OutcomeAssessmentReview] | None:
    """The newest ready assessment of the run that a lawyer accepted (or edited)."""
    row = session.execute(
        select(OutcomeAssessment, OutcomeAssessmentReview)
        .join(
            OutcomeAssessmentReview,
            OutcomeAssessmentReview.assessment_id == OutcomeAssessment.id,
        )
        .where(
            OutcomeAssessment.run_id == run_id,
            OutcomeAssessment.status == "ready",
            OutcomeAssessmentReview.status.in_(tuple(inputs_mod.ACCEPTED)),
        )
        .order_by(OutcomeAssessment.created_at.desc(), OutcomeAssessment.id.desc())
        .limit(1)
    ).first()
    return (row[0], row[1]) if row is not None else None
