"""Cases and hearings (staff). Access: ``lexflow.authz``."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from lexflow import authz, demo
from lexflow.audit import AuditLog, get_audit_log
from lexflow.auth.deps import require_roles, require_user
from lexflow.authz import Action
from lexflow.clock import get_now, get_today
from lexflow.config import Settings, get_settings
from lexflow.db import get_session
from lexflow.domain import ADMINISTRATOR, ADVOCATE
from lexflow.errors import problem_responses
from lexflow.models import User
from lexflow.schemas import (
    CaseCreate,
    CaseDetail,
    CaseSummary,
    CaseUpdate,
    TeamMemberIn,
    UpcomingHearingOut,
)
from lexflow.services import cases as service
from lexflow.services import teams

router = APIRouter(tags=["cases"])


@router.get("/cases", response_model=list[CaseSummary])
def list_cases(
    archived: service.ArchivedFilter = Query(
        default="exclude", description="Archived cases: leave out (default), include, or only."
    ),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    today: date = Depends(get_today),
) -> list[CaseSummary]:
    """The cases you may see (all, for an Administrator), newest first."""
    return service.list_cases(session, today, user, archived)


@router.get(
    "/cases/{case_id}",
    response_model=CaseDetail,
    responses=problem_responses(404),
)
def get_case(
    case_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    today: date = Depends(get_today),
) -> CaseDetail:
    """One case with its documents, hearings, timeline and your permissions on it.

    A case you may not see answers 404, exactly like one that does not exist.
    """
    case, rel = authz.load_case(session, user, service.parse_case_id(case_id), Action.VIEW, audit)
    return service.get_case_detail(session, case.id, today, rel)


@router.post(
    "/cases",
    response_model=CaseDetail,
    status_code=201,
    responses=problem_responses(403, 422),
)
def create_case(
    data: CaseCreate,
    response: Response,
    user: User = Depends(require_roles(ADMINISTRATOR, ADVOCATE)),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    today: date = Depends(get_today),
    settings: Settings = Depends(get_settings),
) -> CaseDetail:
    """Open a new case. The server assigns the case number and opening date.

    Administrators and Advocates only; an Advocate must be the lead (403
    ``field-not-permitted`` otherwise). ``fictional`` (a demo case for a
    fictional client) is accepted only in the verified isolated demo database
    (409 elsewhere).
    """
    allowed = data.fictional and demo.status(session, settings).verified
    case_id = service.create_case(session, data, today, user, audit, fictional_allowed=allowed)
    response.headers["Location"] = f"/api/cases/{case_id}"
    case, rel = authz.load_case(session, user, case_id, Action.VIEW, audit)
    return service.get_case_detail(session, case.id, today, rel)


@router.patch(
    "/cases/{case_id}",
    response_model=CaseDetail,
    responses=problem_responses(403, 404, 422),
)
def update_case(
    case_id: str,
    data: CaseUpdate,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    today: date = Depends(get_today),
) -> CaseDetail:
    """Change some of a case's details. Any change adds a timeline entry by you.

    Each field needs its own permission (``permissions.editableFields`` in the
    case detail); one refused field (403 ``field-not-permitted``) refuses the
    whole request, so nothing changes. Changing the lead advocate or the client
    is for Administrators only.
    """
    parsed = service.parse_case_id(case_id)
    service.update_case(session, parsed, data, today, user, audit)
    case, rel = authz.load_case(session, user, parsed, Action.VIEW, audit)
    return service.get_case_detail(session, case.id, today, rel)


def _detail(
    session: Session, user: User, case_id: uuid.UUID, today: date, audit: AuditLog
) -> CaseDetail:
    case, rel = authz.load_case(session, user, case_id, Action.VIEW, audit)
    return service.get_case_detail(session, case.id, today, rel)


@router.post(
    "/cases/{case_id}/archive",
    response_model=CaseDetail,
    responses=problem_responses(403, 404),
)
def archive_case(
    case_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    today: date = Depends(get_today),
    now: datetime = Depends(get_now),
) -> CaseDetail:
    """Archive a case (Administrators): kept in full, read-only, hidden from lists."""
    parsed = service.parse_case_id(case_id)
    service.set_archived(
        session, parsed, archive=True, today=today, now=now, user=user, audit=audit
    )
    return _detail(session, user, parsed, today, audit)


@router.post(
    "/cases/{case_id}/unarchive",
    response_model=CaseDetail,
    responses=problem_responses(403, 404),
)
def unarchive_case(
    case_id: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    today: date = Depends(get_today),
    now: datetime = Depends(get_now),
) -> CaseDetail:
    """Restore an archived case (Administrators)."""
    parsed = service.parse_case_id(case_id)
    service.set_archived(
        session, parsed, archive=False, today=today, now=now, user=user, audit=audit
    )
    return _detail(session, user, parsed, today, audit)


@router.post(
    "/cases/{case_id}/team",
    response_model=CaseDetail,
    responses=problem_responses(403, 404, 409, 422),
)
def add_team_member(
    case_id: str,
    data: TeamMemberIn,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    today: date = Depends(get_today),
) -> CaseDetail:
    """Add an Advocate (as associate) or a Paralegal to the case team.

    The Administrator or the case's lead advocate only.
    """
    parsed = service.parse_case_id(case_id)
    teams.add_member(session, parsed, data.user_id, today=today, user=user, audit=audit)
    return _detail(session, user, parsed, today, audit)


@router.delete(
    "/cases/{case_id}/team/{member_id}",
    response_model=CaseDetail,
    responses=problem_responses(403, 404, 409),
)
def remove_team_member(
    case_id: str,
    member_id: uuid.UUID,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    audit: AuditLog = Depends(get_audit_log),
    today: date = Depends(get_today),
) -> CaseDetail:
    """Take someone off the case team (the Administrator or the lead advocate)."""
    parsed = service.parse_case_id(case_id)
    teams.remove_member(session, parsed, member_id, today=today, user=user, audit=audit)
    return _detail(session, user, parsed, today, audit)


@router.get("/hearings/upcoming", response_model=list[UpcomingHearingOut])
def upcoming_hearings(
    limit: int = Query(default=5, ge=1, le=50),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    today: date = Depends(get_today),
) -> list[UpcomingHearingOut]:
    """Hearings on or after today on the cases you may see, soonest first."""
    return service.upcoming_hearings(session, today, limit, user)
