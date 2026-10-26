"""Whether this server runs the isolated demo (Milestone 1).

``GET /api/demo``: demo mode on or off, and whether the connected database is
the marked, isolated demo database (``lexflow/demo.py``). The screens offer
fictional demo records only when ``verified`` is true; the server checks again
on every write.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from lexflow import demo
from lexflow.config import Settings, get_settings
from lexflow.db import get_session
from lexflow.schemas import DemoStatusOut

router = APIRouter(tags=["demo"])


@router.get("/demo", response_model=DemoStatusOut)
def demo_status(
    session: Session = Depends(get_session), settings: Settings = Depends(get_settings)
) -> DemoStatusOut:
    found = demo.status(session, settings)
    return DemoStatusOut(enabled=found.enabled, verified=found.verified, reason=found.reason)
