"""AI case analysis runs (Phase 5).

- ``GET  /api/cases/{id}/analysis/setup``: whether the case can be analysed,
  what would be sent (eligible documents) and to which provider;
- ``POST /api/cases/{id}/analysis-runs``: start a run (202, ``queued``);
- ``GET  /api/cases/{id}/analysis-runs``: the case's runs, newest first;
- ``GET  /api/cases/{id}/analysis-runs/{run_id}``: one run and its result.

Access (owner decision D4): starting a run needs ``run-analysis`` on the case
(Administrator, lead or associate advocate; not on an archived case); reading
needs ``view``. Clients never reach these routes (staff router); a case the
user may not see answers 404, exactly like a case that does not exist, so
nothing about its documents or runs is revealed.

Starting a run also requires: analysis configured on the server, migration
0011 applied, the user's confirmation that the selected text goes to the
provider, a sample case unless ``LEXFLOW_AI_ALLOW_CLIENT_DATA`` (D1), ready
documents of this case only, the hourly per-user limit and no other run of
the case waiting or running. Audited: ``analysis.requested`` and
``analysis.viewed`` here, ``analysis.completed``/``failed`` by the worker;
never with text, prompts or keys.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from lexflow import authz
from lexflow.analysis import prompt, runs
from lexflow.analysis.provider import PROVIDER_LABELS, configured_model, unavailable_reason
from lexflow.audit import AuditLog, get_audit_log
from lexflow.auth.deps import require_user
from lexflow.authz import Action
from lexflow.config import Settings, get_settings
from lexflow.db import get_session
from lexflow.errors import ProblemError, problem_responses
from lexflow.models import AnalysisRun, Case, Document, DocumentExtraction, Judgment, User
from lexflow.schemas import (
    ActorOut,
    AnalysisDocumentOut,
    AnalysisEvidenceSummaryOut,
    AnalysisLimitsOut,
    AnalysisResultOut,
    AnalysisRunIn,
    AnalysisRunListOut,
    AnalysisRunOut,
    AnalysisRunSummaryOut,
    AnalysisSetupOut,
)
from lexflow.services import cases as case_service

router = APIRouter(tags=["analysis"])

RUN_NOT_FOUND = "No analysis run with this id exists for this case."
MIGRATION_MISSING = "AI analysis needs a database update (migration 0011) that is not applied yet."
HISTORY_MAX = 50


def _now() -> datetime:
    return datetime.now(UTC)


def _unavailable(settings: Settings, session: Session) -> tuple[str, str] | None:
    if not runs.table_exists(session):
        return "migration-missing", MIGRATION_MISSING
    missing = unavailable_reason(settings)
    return (missing.code, missing.reason) if missing is not None else None


def _documents(session: Session, case: Case) -> list[AnalysisDocumentOut]:
    rows = session.execute(
        select(Document, DocumentExtraction)
        .outerjoin(DocumentExtraction, DocumentExtraction.document_id == Document.id)
        .where(Document.case_id == case.id, Document.deleted_at.is_(None))
        .order_by(Document.uploaded_on, func.lower(Document.name), Document.id)
    ).all()
    return [
        AnalysisDocumentOut(
            id=document.id,
            name=document.name,
            eligible=job is not None and job.status == "ready",
            section_count=job.section_count if job is not None else None,
            page_count=job.page_count if job is not None else None,
        )
        for document, job in rows
    ]


def _summary(run: AnalysisRun, people: dict[uuid.UUID, User]) -> AnalysisRunSummaryOut:
    who = people.get(run.requested_by_id) if run.requested_by_id else None
    return AnalysisRunSummaryOut(
        id=run.id,
        case_id=run.case_id,
        status=run.status,  # type: ignore[arg-type]  # the database checks the value
        reason_code=run.reason_code,
        reason=run.reason,
        provider=run.provider,
        model=run.model,
        prompt_version=run.prompt_version,
        requested_by=ActorOut(id=who.id, name=who.name) if who is not None else None,
        document_count=len(run.selection.get("documentIds", [])),
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


def _people(session: Session, items: list[AnalysisRun]) -> dict[uuid.UUID, User]:
    ids = {r.requested_by_id for r in items if r.requested_by_id is not None}
    if not ids:
        return {}
    return {u.id: u for u in session.scalars(select(User).where(User.id.in_(ids)))}


def _full(session: Session, run: AnalysisRun) -> AnalysisRunOut:
    evidence = None
    if run.evidence is not None:
        items = run.evidence.get("items", {})
        documents = {v["documentId"] for v in items.values() if v.get("kind") == "document"}
        evidence = AnalysisEvidenceSummaryOut(
            documents=len(documents),
            passages=sum(1 for v in items.values() if v.get("kind") == "document"),
            judgment_passages=sum(1 for v in items.values() if v.get("kind") == "judgment"),
            characters=int(run.evidence.get("characters", 0)),
            truncated=bool(run.evidence.get("truncated", False)),
        )
    result = (
        AnalysisResultOut.model_validate(run.result)
        if run.status == "ready" and run.result is not None
        else None
    )
    summary = _summary(run, _people(session, [run]))
    return AnalysisRunOut(**summary.model_dump(), evidence=evidence, result=result)


@router.get(
    "/cases/{case_id}/analysis/setup",
    response_model=AnalysisSetupOut,
    responses=problem_responses(404),
)
def analysis_setup(
    case_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    settings: Settings = Depends(get_settings),
) -> AnalysisSetupOut:
    """What an analysis of this case would use, and whether it can start now."""
    case, rel = authz.load_case(
        session, user, case_service.parse_case_id(case_id), Action.VIEW, audit
    )
    unavailable = _unavailable(settings, session)
    sample_only = not settings.ai_allow_client_data
    active = runs.active_run(session, case.id) if unavailable is None else None
    cannot: str | None = None
    if unavailable is not None:
        cannot = unavailable[1]
    elif not authz.allows(rel, Action.RUN_ANALYSIS):
        cannot = "Only the case's advocates and administrators may start an analysis."
    elif case.archived_at is not None:
        cannot = "This case is archived."
    elif sample_only and not case.is_sample:
        cannot = (
            "Only sample (fictional) cases may be analysed on this server until a privacy, "
            "confidentiality and provider-terms review allows client material."
        )
    elif active is not None:
        cannot = "An analysis of this case is already waiting or running."
    provider = settings.ai_provider if settings.ai_provider != "disabled" else None
    return AnalysisSetupOut(
        available=unavailable is None,
        unavailable_reason=unavailable[1] if unavailable is not None else None,
        provider=provider,
        provider_label=PROVIDER_LABELS.get(provider) if provider else None,
        model=configured_model(settings),
        prompt_version=prompt.PROMPT_VERSION,
        can_run=cannot is None,
        cannot_run_reason=cannot,
        sample_only=sample_only,
        case_is_sample=case.is_sample,
        documents=_documents(session, case),
        judgments_available=session.scalar(select(func.count()).select_from(Judgment)) or 0,
        limits=AnalysisLimitsOut(
            max_documents=settings.ai_max_documents,
            max_input_chars=settings.ai_max_input_chars,
            max_precedents=settings.ai_max_precedents,
            runs_per_hour=settings.ai_runs_per_user_per_hour,
        ),
        active_run_id=active.id if active is not None else None,
    )


@router.post(
    "/cases/{case_id}/analysis-runs",
    response_model=AnalysisRunOut,
    status_code=status.HTTP_202_ACCEPTED,
    responses=problem_responses(403, 404, 409, 422, 429, 503),
)
def start_analysis(
    case_id: str,
    body: AnalysisRunIn,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    settings: Settings = Depends(get_settings),
) -> AnalysisRunOut:
    """Queue an analysis of the selected documents. The worker sends their text
    (and any matching judgment passages) to the configured provider."""
    case, _ = authz.load_case(
        session, user, case_service.parse_case_id(case_id), Action.RUN_ANALYSIS, audit
    )
    unavailable = _unavailable(settings, session)
    if unavailable is not None:
        raise ProblemError(503, "analysis-unavailable", unavailable[1])
    if not body.confirm_transmission:
        raise ProblemError(
            422,
            "confirmation-required",
            "Confirm that the selected text may be sent to the AI provider.",
        )
    if not settings.ai_allow_client_data and not case.is_sample:
        raise ProblemError(
            403,
            "client-data-not-allowed",
            "Only sample (fictional) cases may be analysed on this server.",
        )
    document_ids = list(dict.fromkeys(body.document_ids))
    if len(document_ids) > settings.ai_max_documents:
        raise ProblemError(
            422,
            "too-many-documents",
            f"Select at most {settings.ai_max_documents} documents.",
        )
    eligible = {d.id for d in _documents(session, case) if d.eligible and d.id in set(document_ids)}
    if len(eligible) != len(document_ids):
        raise ProblemError(
            422,
            "document-not-eligible",
            "Select only documents of this case whose text is ready.",
        )
    now = _now()
    if (
        runs.runs_since(session, user.id, now - timedelta(hours=1))
        >= settings.ai_runs_per_user_per_hour
    ):
        raise ProblemError(
            429,
            "rate-limited",
            f"You can start at most {settings.ai_runs_per_user_per_hour} analyses an hour. "
            "Try again later.",
        )
    if runs.active_run(session, case.id) is not None:
        raise ProblemError(
            409, "analysis-running", "An analysis of this case is already waiting or running."
        )
    model = configured_model(settings) or settings.ai_provider
    try:
        with session.begin_nested():
            run = runs.create(
                session,
                case,
                requested_by=user.id,
                document_ids=document_ids,
                provider=settings.ai_provider,
                model=model,
                settings=settings,
                now=now,
            )
    except IntegrityError:
        raise ProblemError(
            409, "analysis-running", "An analysis of this case is already waiting or running."
        ) from None
    session.commit()
    audit.record(
        "analysis.requested",
        actor=user,
        target_type="analysis_run",
        target_id=run.id,
        case_id=case.id,
        details={
            "documents": len(document_ids),
            "provider": run.provider,
            "model": run.model,
            "promptVersion": run.prompt_version,
        },
    )
    return _full(session, run)


@router.get(
    "/cases/{case_id}/analysis-runs",
    response_model=AnalysisRunListOut,
    responses=problem_responses(404),
)
def list_analyses(
    case_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
) -> AnalysisRunListOut:
    """The case's analysis runs, newest first (at most 50), without results."""
    case, _ = authz.load_case(
        session, user, case_service.parse_case_id(case_id), Action.VIEW, audit
    )
    if not runs.table_exists(session):
        return AnalysisRunListOut(items=[])
    items = list(
        session.scalars(
            select(AnalysisRun)
            .where(AnalysisRun.case_id == case.id)
            .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id)
            .limit(HISTORY_MAX)
        )
    )
    people = _people(session, items)
    return AnalysisRunListOut(items=[_summary(r, people) for r in items])


@router.get(
    "/cases/{case_id}/analysis-runs/{run_id}",
    response_model=AnalysisRunOut,
    responses=problem_responses(404),
)
def get_analysis(
    case_id: str,
    run_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
) -> AnalysisRunOut:
    """One run of this case, with its validated result when it is ready."""
    case, _ = authz.load_case(
        session, user, case_service.parse_case_id(case_id), Action.VIEW, audit
    )
    try:
        parsed = uuid.UUID(run_id)
    except ValueError:
        raise ProblemError(404, "analysis-run-not-found", RUN_NOT_FOUND) from None
    run = session.get(AnalysisRun, parsed) if runs.table_exists(session) else None
    if run is None or run.case_id != case.id:
        raise ProblemError(404, "analysis-run-not-found", RUN_NOT_FOUND)
    if run.status == "ready":
        audit.record(
            "analysis.viewed",
            actor=user,
            target_type="analysis_run",
            target_id=run.id,
            case_id=case.id,
        )
    return _full(session, run)
