"""Analysis runs: the queue (``analysis_runs``) and the worker's step.

The API creates a run ``queued``. The worker claims it like an extraction job
(``FOR UPDATE SKIP LOCKED`` and a lease), then:

1. re-checks the case: it must still exist, not be archived, and be a sample
   case unless client data is allowed (owner decision D1);
2. assembles the evidence (``evidence``); with no passage at all the run is
   ``ready`` with an "insufficient evidence" result and **no provider call**;
3. renders the prompt and calls the provider, outside any database
   transaction; an answer that is not usable JSON (or was cut off) is asked
   for once more, then the run fails ``invalid-output``;
4. validates the answer against the evidence (``validation``) and stores only
   the validated result, the evidence references and the token counts.

A busy or unreachable provider puts the run back in the queue with a pause,
up to ``LEXFLOW_AI_MAX_ATTEMPTS`` tries in all. Every outcome is stored only
while this worker still holds the run, and is audited in the same
transaction (counts, model and prompt version; never text).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.orm import Session

from lexflow.analysis import evidence as evidence_mod
from lexflow.analysis import output, prompt, validation
from lexflow.analysis.provider import (
    AnalysisProvider,
    ProviderError,
    Request,
    client_data_allowed,
)
from lexflow.audit import Actor, build_event
from lexflow.config import Settings
from lexflow.models import AnalysisRun, Case
from lexflow.schemas import AnalysisResultOut

logger = logging.getLogger("lexflow.analysis")

Sessions = Callable[[], AbstractContextManager[Session]]
ACTIVE = ("queued", "running")
RETRY_PAUSE_SECONDS = 30
INTERRUPTED = "The analysis stopped unexpectedly too many times. Start it again later."
PROVIDER_FAULT = "The AI provider failed in an unexpected way. Start the analysis again later."
CHECK_FAULT = "LexFlow could not check the model's answer, so nothing from it is shown."
WORKER = Actor(None, "analysis worker", "System")


def table_exists(session: Session) -> bool:
    """False before migration 0011: analysis is then unavailable, nothing fails."""
    return session.scalar(text("SELECT to_regclass('analysis_runs')")) is not None


def limits_from(settings: Settings) -> evidence_mod.Limits:
    return evidence_mod.Limits(
        max_documents=settings.ai_max_documents,
        max_passages=settings.ai_max_passages,
        max_precedents=settings.ai_max_precedents,
        max_chars=settings.ai_max_input_chars,
        judgment_origin="synthetic" if settings.outcome_assessment else None,
    )


def active_run(session: Session, case_id: uuid.UUID) -> AnalysisRun | None:
    return session.scalar(
        select(AnalysisRun).where(AnalysisRun.case_id == case_id, AnalysisRun.status.in_(ACTIVE))
    )


def runs_since(session: Session, user_id: uuid.UUID, since: datetime) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(AnalysisRun)
            .where(AnalysisRun.requested_by_id == user_id, AnalysisRun.created_at >= since)
        )
        or 0
    )


def create(
    session: Session,
    case: Case,
    *,
    requested_by: uuid.UUID,
    document_ids: list[uuid.UUID],
    provider: str,
    model: str,
    settings: Settings,
    now: datetime,
) -> AnalysisRun:
    """A queued run. The caller commits (and maps the one-active-run index)."""
    run = AnalysisRun(
        case_id=case.id,
        requested_by_id=requested_by,
        status="queued",
        provider=provider,
        model=model,
        prompt_version=prompt.PROMPT_VERSION,
        available_at=now,
        created_at=now,
        selection={
            "documentIds": [str(d) for d in document_ids],
            "limits": {
                "maxDocuments": settings.ai_max_documents,
                "maxPassages": settings.ai_max_passages,
                "maxPrecedents": settings.ai_max_precedents,
                "maxInputChars": settings.ai_max_input_chars,
                "maxOutputTokens": settings.ai_max_output_tokens,
            },
        },
    )
    session.add(run)
    session.flush()
    return run


def claim(
    session: Session, *, worker_id: str, now: datetime, lease_seconds: int, max_attempts: int
) -> uuid.UUID | None:
    """Take the oldest run that is due (or whose worker's lease expired). Commits."""
    abandoned = (
        session.execute(
            update(AnalysisRun)
            .where(
                AnalysisRun.status == "running",
                AnalysisRun.lease_expires_at < now,
                AnalysisRun.attempts >= max_attempts,
            )
            .values(
                status="failed",
                reason_code="interrupted",
                reason=INTERRUPTED,
                lease_expires_at=None,
                worker_id=None,
                finished_at=now,
            )
            .returning(AnalysisRun.id, AnalysisRun.case_id)
        )
        .tuples()
        .all()
    )
    for run_id, case_id in abandoned:
        session.add(_event("analysis.failed", run_id, case_id, "failed", {"reason": "interrupted"}))
        logger.warning("analysis %s: abandoned after %d attempts", run_id, max_attempts)
    candidate = (
        select(AnalysisRun.id)
        .where(
            or_(
                and_(AnalysisRun.status == "queued", AnalysisRun.available_at <= now),
                and_(AnalysisRun.status == "running", AnalysisRun.lease_expires_at < now),
            )
        )
        .order_by(AnalysisRun.available_at, AnalysisRun.created_at, AnalysisRun.id)
        .limit(1)
        .with_for_update(skip_locked=True)
        .scalar_subquery()
    )
    claimed = session.execute(
        update(AnalysisRun)
        .where(AnalysisRun.id == candidate)
        .values(
            status="running",
            attempts=AnalysisRun.attempts + 1,
            started_at=now,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
            worker_id=worker_id,
        )
        .returning(AnalysisRun.id)
    ).scalar_one_or_none()
    session.commit()
    return claimed


@dataclass(frozen=True)
class Ready:
    result: AnalysisResultOut
    evidence: dict[str, Any]
    usage: dict[str, int]
    provider: str
    model: str
    called: bool


@dataclass(frozen=True)
class Failed:
    code: str
    message: str
    retry: bool = False
    evidence: dict[str, Any] | None = None
    usage: dict[str, int] | None = None
    # Validated provider codes (see ProviderError.diagnostic): for the worker
    # log and the administrator-only audit log, never for the stored reason.
    diagnostic: dict[str, str] | None = None


def _event(
    action: str, run_id: uuid.UUID, case_id: uuid.UUID, outcome: str, details: dict[str, Any]
) -> Any:
    return build_event(
        action,
        actor=WORKER,
        outcome=outcome,
        target_type="analysis_run",
        target_id=run_id,
        case_id=case_id,
        details=details,
    )


def retry_due(outcome: Failed, attempts: int, max_attempts: int) -> bool:
    """Whether a failed attempt goes back to the queue (``attempts`` counts the
    attempt that just failed)."""
    return outcome.retry and attempts < max_attempts


def complete(
    session: Session,
    run_id: uuid.UUID,
    *,
    worker_id: str,
    outcome: Ready | Failed,
    now: datetime,
    max_attempts: int,
) -> str:
    """Store the outcome if this worker still holds the run. Commits. Returns
    the new status, or ``"discarded"``."""
    run = session.get(AnalysisRun, run_id, with_for_update=True, populate_existing=True)
    if run is None or run.status != "running" or run.worker_id != worker_id:
        session.rollback()
        logger.warning("analysis %s: result discarded (the run is no longer ours)", run_id)
        return "discarded"
    run.lease_expires_at, run.worker_id = None, None
    if isinstance(outcome, Failed):
        if retry_due(outcome, run.attempts, max_attempts):
            run.status = "queued"
            run.available_at = now + timedelta(seconds=RETRY_PAUSE_SECONDS * run.attempts)
            session.commit()
            return "queued"
        run.status, run.reason_code, run.reason = "failed", outcome.code, outcome.message
        run.evidence = outcome.evidence
        run.usage = outcome.usage
        run.finished_at = now
        session.add(
            _event(
                "analysis.failed",
                run.id,
                run.case_id,
                "failed",
                {
                    "reason": outcome.code,
                    "attempts": run.attempts,
                    "model": run.model,
                    **{
                        f"provider{k[0].upper()}{k[1:]}": v
                        for k, v in (outcome.diagnostic or {}).items()
                    },
                },
            )
        )
        session.commit()
        return "failed"
    result = outcome.result
    run.status = "ready"
    run.provider, run.model = outcome.provider, outcome.model
    run.result = result.model_dump(mode="json", by_alias=True)
    run.removed = result.removed.model_dump(mode="json", by_alias=True)
    run.evidence = outcome.evidence
    run.usage = outcome.usage
    run.finished_at = now
    session.add(
        _event(
            "analysis.completed",
            run.id,
            run.case_id,
            "success",
            {
                "provider": outcome.provider,
                "model": outcome.model,
                "promptVersion": run.prompt_version,
                "schemaVersion": output.RESPONSE_SCHEMA_VERSION,
                "validatorVersion": validation.VALIDATOR_VERSION,
                "providerCalled": outcome.called,
                "facts": len(result.facts),
                "issues": len(result.issues),
                "precedents": len(result.precedents),
                "contradictions": len(result.contradictions),
                "removed": result.removed.count,
                "insufficientEvidence": result.insufficient_evidence,
            },
        )
    )
    session.commit()
    return "ready"


def _gate(case: Case | None, settings: Settings) -> Failed | None:
    if case is None:
        return Failed("case-missing", "The case no longer exists.")
    if case.archived_at is not None:
        return Failed("case-archived", "The case was archived before the analysis ran.")
    if not case.is_sample and not client_data_allowed(settings, case.id):
        return Failed(
            "client-data-not-allowed",
            "Only sample (fictional) cases may be analysed on this server.",
        )
    return None


PROVIDER_MISMATCH = (
    "This analysis was confirmed for a different AI provider than the one this server "
    "now uses, so nothing was sent. Start a new analysis to use the current provider."
)


def pipeline_record() -> dict[str, str]:
    """Which instructions, response schema and validation rules produced a
    result, stored with the run's evidence record (from M9 on)."""
    return {
        "promptVersion": prompt.PROMPT_VERSION,
        "schemaVersion": output.RESPONSE_SCHEMA_VERSION,
        "schemaSha256": output.schema_sha256(),
        "validatorVersion": validation.VALIDATOR_VERSION,
    }


def _merge(total: dict[str, int], more: dict[str, int]) -> None:
    for key, value in more.items():
        total[key] = total.get(key, 0) + value


def analyse(
    session_factory: Sessions,
    provider: AnalysisProvider,
    settings: Settings,
    run_id: uuid.UUID,
) -> Ready | Failed | None:
    """Do the work of one claimed run (no database transaction is held while
    the provider is called). None when the run disappeared meanwhile."""
    with session_factory() as session:
        run = session.get(AnalysisRun, run_id)
        if run is None:
            return None
        # The person who started the run confirmed sending text to this provider;
        # if the worker now has another one, nothing may be sent to it.
        if run.provider != provider.name:
            return Failed("provider-mismatch", PROVIDER_MISMATCH)
        case = session.get(Case, run.case_id)
        refused = _gate(case, settings)
        if refused is not None or case is None:
            return refused
        document_ids = [uuid.UUID(d) for d in run.selection.get("documentIds", [])]
        limits = limits_from(settings)
        if settings.ai_provider == "prepared" or case.id in settings.ai_approved_case_ids:
            from lexflow.analysis.prepared import pinned_judgments

            limits = replace(limits, pinned=pinned_judgments(case.title))
        if case.id in settings.ai_approved_case_ids:
            limits = replace(limits, judgment_origin=None)  # genuine judgments approved
        evidence = evidence_mod.assemble(session, case, document_ids, limits)
    return check_answer(provider, evidence, settings.ai_max_output_tokens, label=str(run_id))


def check_answer(
    provider: AnalysisProvider,
    evidence: evidence_mod.Evidence,
    max_output_tokens: int,
    *,
    label: str,
) -> Ready | Failed:
    """Send assembled evidence to the provider and keep only what validates.
    No database access: the worker calls it for a run, and the offline
    evaluation (``scripts/evaluate_analysis.py``) with a scripted provider."""
    record = {**evidence.record(), "pipeline": pipeline_record()}
    if not evidence.passages:
        return Ready(
            validation.insufficient(evidence),
            record,
            {},
            provider.name,
            provider.model,
            called=False,
        )
    request = Request(
        system_instruction=prompt.SYSTEM_INSTRUCTION,
        prompt=prompt.render(evidence),
        response_schema=output.RESPONSE_SCHEMA,
        max_output_tokens=max_output_tokens,
        evidence=evidence,
    )
    usage: dict[str, int] = {}
    problem = output.InvalidOutputError("invalid-output", "The answer could not be read.")
    for _ in range(2):  # one more try for an unreadable or cut-off answer
        try:
            response = provider.generate(request)
        except ProviderError as error:
            return Failed(
                error.code, error.message, error.retry, record, usage, diagnostic=error.diagnostic
            )
        except Exception as error:  # an SDK or provider bug must not crash the worker
            # Only the type is logged: an exception's text could echo the request.
            logger.error("analysis %s: provider raised %s", label, type(error).__name__)
            return Failed("provider-error", PROVIDER_FAULT, evidence=record, usage=usage)
        _merge(usage, response.usage)
        if response.truncated:
            problem = output.InvalidOutputError(
                "invalid-output", "The answer was cut off at the output limit."
            )
            continue
        try:
            parsed = output.parse(response.text)
            result = validation.validate(parsed, evidence)
        except output.InvalidOutputError as error:
            problem = error
            continue
        except Exception as error:  # never store an answer that was not fully checked
            logger.error("analysis %s: checking the answer raised %s", label, type(error).__name__)
            return Failed("validation-error", CHECK_FAULT, evidence=record, usage=usage)
        return Ready(result, record, usage, provider.name, provider.model, called=True)
    return Failed(
        "invalid-output",
        f"The model's answer could not be used twice in a row: {problem.message}",
        evidence=record,
        usage=usage,
    )


def process(
    sessions: Sessions,
    provider: AnalysisProvider,
    settings: Settings,
    run_id: uuid.UUID,
    worker_id: str,
    *,
    now: Callable[[], datetime],
) -> str:
    outcome = analyse(sessions, provider, settings, run_id)
    if outcome is None:
        return "discarded"
    with sessions() as session:
        status = complete(
            session,
            run_id,
            worker_id=worker_id,
            outcome=outcome,
            now=now(),
            max_attempts=settings.ai_max_attempts,
        )
    if isinstance(outcome, Failed):
        codes = "".join(f" {k}={v}" for k, v in (outcome.diagnostic or {}).items())
        logger.info("analysis %s: %s (%s)%s", run_id, status, outcome.code, codes)
    else:
        logger.info(
            "analysis %s: %s (%d facts, %d removed)",
            run_id,
            status,
            len(outcome.result.facts),
            outcome.result.removed.count,
        )
    return status


def release(
    sessions: Sessions,
    run_id: uuid.UUID,
    worker_id: str,
    *,
    max_attempts: int,
    now: datetime,
) -> None:
    """Hand an interrupted run back to the queue (if this worker still holds
    it), or fail it as interrupted when it has used its last attempt, so a run
    that keeps stopping the worker cannot be claimed forever."""
    with sessions() as session:
        held = (
            AnalysisRun.id == run_id,
            AnalysisRun.status == "running",
            AnalysisRun.worker_id == worker_id,
        )
        failed = session.execute(
            update(AnalysisRun)
            .where(*held, AnalysisRun.attempts >= max_attempts)
            .values(
                status="failed",
                reason_code="interrupted",
                reason=INTERRUPTED,
                lease_expires_at=None,
                worker_id=None,
                finished_at=now,
            )
            .returning(AnalysisRun.case_id)
        ).scalar_one_or_none()
        if failed is not None:
            session.add(
                _event("analysis.failed", run_id, failed, "failed", {"reason": "interrupted"})
            )
        else:
            session.execute(
                update(AnalysisRun)
                .where(*held)
                .values(status="queued", lease_expires_at=None, worker_id=None)
            )
        session.commit()
