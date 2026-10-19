"""Cases and hearings."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from lexflow.clock import get_today
from lexflow.db import get_session
from lexflow.errors import problem_responses
from lexflow.schemas import CaseCreate, CaseDetail, CaseSummary, CaseUpdate, UpcomingHearingOut
from lexflow.services import cases as service

router = APIRouter(tags=["cases"])


@router.get("/cases", response_model=list[CaseSummary])
def list_cases(
    session: Session = Depends(get_session), today: date = Depends(get_today)
) -> list[CaseSummary]:
    """Every case, newest first, with what the case list needs."""
    return service.list_cases(session, today)


@router.get(
    "/cases/{case_id}",
    response_model=CaseDetail,
    responses=problem_responses(404),
)
def get_case(
    case_id: str, session: Session = Depends(get_session), today: date = Depends(get_today)
) -> CaseDetail:
    """One case with its documents, hearings and timeline."""
    return service.get_case_detail(session, service.parse_case_id(case_id), today)


@router.post(
    "/cases",
    response_model=CaseDetail,
    status_code=201,
    responses=problem_responses(422),
)
def create_case(
    data: CaseCreate,
    response: Response,
    session: Session = Depends(get_session),
    today: date = Depends(get_today),
) -> CaseDetail:
    """Open a new case. The server assigns the case number and opening date."""
    case_id = service.create_case(session, data, today)
    response.headers["Location"] = f"/api/cases/{case_id}"
    return service.get_case_detail(session, case_id, today)


@router.patch(
    "/cases/{case_id}",
    response_model=CaseDetail,
    responses=problem_responses(404, 422),
)
def update_case(
    case_id: str,
    data: CaseUpdate,
    session: Session = Depends(get_session),
    today: date = Depends(get_today),
) -> CaseDetail:
    """Change some of a case's details. Any change adds a timeline entry.

    Phase 1 has no sign-in, so the entry records no actor.
    """
    parsed = service.parse_case_id(case_id)
    service.update_case(session, parsed, data, today)
    return service.get_case_detail(session, parsed, today)


@router.get("/hearings/upcoming", response_model=list[UpcomingHearingOut])
def upcoming_hearings(
    limit: int = Query(default=5, ge=1, le=50),
    session: Session = Depends(get_session),
    today: date = Depends(get_today),
) -> list[UpcomingHearingOut]:
    """Hearings on or after today across all cases, soonest first."""
    return service.upcoming_hearings(session, today, limit)
