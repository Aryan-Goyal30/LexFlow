"""Two first decisions on the same outcome assessment at the same time (Phase 7
demo), with real commits on the test database, as ``test_review_race.py`` does
for findings. SYNTHETIC rows only; no provider is called.

Connection A records the first decision and keeps its transaction open; the
second reviewer, who also saw no review, sends a first decision through the
API. The test waits until the database shows that request blocked behind A,
then commits A. Exactly one decision may survive, and the second reviewer must
receive 409 "review-changed".
"""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from lexflow.assessment import service
from lexflow.config import Settings, get_settings
from lexflow.models import (
    AuditEvent,
    OutcomeAssessment,
    OutcomeAssessmentReview,
    OutcomeAssessmentReviewEvent,
    User,
)
from lexflow.seed.loader import load_sample_data
from lexflow.services.reviews import Change
from tests.access_fixtures import SATTVIK
from tests.conftest import committed_user, http_client, sign_in_as
from tests.review_fixtures import ready_run

WAIT_SECONDS = 30.0
BLOCKED_BEHIND = text(
    "select count(*) from pg_stat_activity "
    "where datname = current_database() and :holder = any(pg_blocking_pids(pid))"
)


def settings(**values: Any) -> Settings:
    """Settings from environment-style names (as ``LEXFLOW_OUTCOME_ASSESSMENT``)."""
    return Settings(**values)


@pytest.fixture
def real_app(committed_engine: Engine) -> FastAPI:
    from lexflow.main import create_app

    app = create_app()
    flag_on = settings(LEXFLOW_OUTCOME_ASSESSMENT=True)
    app.dependency_overrides[get_settings] = lambda: flag_on  # the database is not overridden
    return app


def test_a_simultaneous_first_decision_on_an_assessment_is_refused(
    committed_engine: Engine, real_app: FastAPI
) -> None:
    email = committed_user(committed_engine)
    with Session(committed_engine) as setup:
        load_sample_data(setup)
        setup.commit()
        run = ready_run(setup, SATTVIK)
        assessment = OutcomeAssessment(
            run_id=run.id,
            case_id=SATTVIK,
            status="ready",
            provider="scripted",
            model="scripted-assessment-v1",
            prompt_version="outcome-assessment-v1",
            inputs={"findings": [], "precedents": [], "excluded": {}},
            result={"summary": "SYNTHETIC demonstration summary."},
            created_at=datetime.now(UTC),
        )
        setup.add(assessment)
        setup.commit()
        run_id, assessment_id = run.id, assessment.id
        actor = setup.scalar(select(User.id).where(User.email == email))
    assert actor is not None

    with http_client(real_app, raise_server_exceptions=False) as http:
        sign_in_as(http, email)
        first = Session(committed_engine)
        try:
            held = first.get(OutcomeAssessment, assessment_id)
            assert held is not None
            service.apply_review(
                first,
                held,
                Change("accepted", None, None),
                expected_version=0,
                actor_id=actor,
                now=datetime.now(UTC),
            )  # flushed, not committed: A holds the assessment's unique-index entry
            holder = first.scalar(select(func.pg_backend_pid()))
            second: dict[str, Any] = {}

            def second_reviewer() -> None:
                second["response"] = http.put(
                    f"/api/cases/{SATTVIK}/analysis-runs/{run_id}/assessments/"
                    f"{assessment_id}/review",
                    json={"status": "rejected", "expectedVersion": 0, "note": "late"},
                )

            thread = threading.Thread(target=second_reviewer)
            thread.start()
            blocked = 0
            deadline = time.monotonic() + WAIT_SECONDS
            while thread.is_alive() and time.monotonic() < deadline:
                with committed_engine.connect() as watcher:  # a fresh snapshot each time
                    blocked = watcher.scalar(BLOCKED_BEHIND, {"holder": holder}) or 0
                if blocked:
                    break
                time.sleep(0.05)
            assert blocked, (
                "the second request was never seen waiting behind the first decision: "
                f"{second.get('response') and second['response'].text}"
            )
            first.commit()
        finally:
            first.close()
        thread.join(timeout=WAIT_SECONDS)
        assert not thread.is_alive()

    response = second["response"]
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "review-changed"
    with Session(committed_engine) as check:
        stored = check.scalars(select(OutcomeAssessmentReview)).all()
        assert [(r.status, r.version, r.note) for r in stored] == [("accepted", 1, None)]
        count = select(func.count()).select_from(OutcomeAssessmentReviewEvent)
        assert check.scalar(count) == 1
        refused = check.scalars(
            select(AuditEvent).where(AuditEvent.action == "assessment.reviewed")
        ).all()
        assert refused == []
