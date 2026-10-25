"""Two first decisions on the same finding at the same time (Phase 6), with
real commits on the test database. SYNTHETIC run only; no provider is called.

Ordinary tests share one rolled-back transaction, so they cannot show two
reviewers racing. Here connection A records the first decision and keeps its
transaction open; the second reviewer, who also saw no review, sends the same
first decision through the API. The test waits until the database shows that
request blocked behind A, then commits A, so the order is fixed rather than
left to timing. Exactly one decision may survive, and the second reviewer must
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

from lexflow.models import (
    AnalysisFindingReview,
    AnalysisFindingReviewEvent,
    AnalysisRun,
    AuditEvent,
    User,
)
from lexflow.seed.loader import load_sample_data
from lexflow.services import reviews
from tests.access_fixtures import SATTVIK
from tests.conftest import committed_user, http_client, sign_in_as
from tests.review_fixtures import ready_run

WAIT_SECONDS = 30.0

# Run in a fresh transaction each time: PostgreSQL keeps one activity snapshot
# per transaction, so polling inside a single transaction can miss the wait.
BLOCKED_BEHIND = text(
    "select count(*) from pg_stat_activity "
    "where datname = current_database() and :holder = any(pg_blocking_pids(pid))"
)


@pytest.fixture
def real_app(committed_engine: Engine) -> FastAPI:
    from lexflow.main import create_app

    return create_app()  # no dependency overrides: each request commits for real


def test_a_simultaneous_first_decision_is_refused_and_one_review_remains(
    committed_engine: Engine, real_app: FastAPI
) -> None:
    email = committed_user(committed_engine)
    with Session(committed_engine) as setup:
        load_sample_data(setup)
        setup.commit()
        run_id = ready_run(setup, SATTVIK).id
        actor = setup.scalar(select(User.id).where(User.email == email))
    assert actor is not None

    with http_client(real_app, raise_server_exceptions=False) as http:
        sign_in_as(http, email)

        first = Session(committed_engine)
        try:
            run = first.get(AnalysisRun, run_id)
            assert run is not None
            finding = reviews.finding(run.result, "F1")
            assert finding is not None
            reviews.apply(
                first,
                run,
                finding,
                reviews.Change("accepted", None, None),
                expected_version=0,
                actor_id=actor,
                now=datetime.now(UTC),
            )  # flushed, not committed: A holds the finding's unique-index entry
            holder = first.scalar(select(func.pg_backend_pid()))

            second: dict[str, Any] = {}

            def second_reviewer() -> None:
                second["response"] = http.put(
                    f"/api/cases/{SATTVIK}/analysis-runs/{run_id}/reviews/F1",
                    json={"status": "rejected", "expectedVersion": 0, "note": "late"},
                )

            thread = threading.Thread(target=second_reviewer)
            thread.start()
            blocked = 0
            deadline = time.monotonic() + WAIT_SECONDS
            while thread.is_alive() and time.monotonic() < deadline:
                with committed_engine.connect() as watcher:
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
        stored = check.scalars(select(AnalysisFindingReview)).all()
        assert [(r.finding_id, r.status, r.version, r.note) for r in stored] == [
            ("F1", "accepted", 1, None)
        ]
        assert check.scalar(select(func.count()).select_from(AnalysisFindingReviewEvent)) == 1
        refused = check.scalars(
            select(AuditEvent).where(AuditEvent.action == "analysis.finding_reviewed")
        ).all()
        assert refused == []  # the refused request is not audited as a review
