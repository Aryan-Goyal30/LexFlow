"""Probe (not part of the repository): two first decisions on the same finding
at the same time, on the disposable test database with real commits.

A writes its decision and holds the transaction open; B, which also saw no
review, tries to insert its own and must wait on the unique index; when A
commits, B fails with a unique violation (the API maps it to 409
"review-changed"). Exactly one review row and one history entry remain.

Whatever the interleaving, B must be refused: by the unique index (it inserted
while, or after, A's row existed) or by the version check (it read after A
committed). Whether a third connection *saw* B waiting is timing-dependent and
recorded for information only; the assertions are on the outcome."""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime

from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from lexflow.models import (
    AnalysisFindingReview,
    AnalysisFindingReviewEvent,
    AnalysisRun,
)
from lexflow.seed import sample_uuid
from lexflow.seed.loader import load_sample_data
from lexflow.services import reviews
from tests.access_fixtures import SATTVIK
from tests.review_fixtures import ready_run


def test_two_first_decisions_at_the_same_time(committed_engine: Engine) -> None:
    with Session(committed_engine) as setup:
        load_sample_data(setup)
        setup.commit()
        run_id = ready_run(setup, SATTVIK).id
    actor = sample_uuid("advocate", "Aryan Goyal")
    now = datetime.now(UTC)

    a = Session(committed_engine)
    run_a = a.get(AnalysisRun, run_id)
    assert run_a is not None
    item = reviews.finding(run_a.result, "F1")
    assert item is not None
    reviews.apply(
        a,
        run_a,
        item,
        reviews.Change("accepted", None, None),
        expected_version=0,
        actor_id=actor,
        now=now,
    )  # flushed, not committed: the row and its unique-index entry are held by A

    outcome: dict[str, object] = {}

    def second_reviewer() -> None:
        with Session(committed_engine) as b:
            run_b = b.get(AnalysisRun, run_id)
            assert run_b is not None
            try:
                reviews.apply(
                    b,
                    run_b,
                    item,
                    reviews.Change("rejected", None, "late"),
                    expected_version=0,
                    actor_id=actor,
                    now=now,
                )
                b.commit()
                outcome["b"] = "committed"
            except IntegrityError as error:
                b.rollback()
                outcome["b"] = f"IntegrityError: {type(error.orig).__name__}"
            except reviews.StaleVersionError as stale:
                b.rollback()
                outcome["b"] = f"StaleVersionError({stale.current_version})"

    thread = threading.Thread(target=second_reviewer)
    thread.start()
    # Wait until B is really blocked on A's lock (seen from a third connection).
    with committed_engine.connect() as watcher:
        for _ in range(400):  # up to 20 s for B to reach its insert
            waiting = watcher.scalar(
                text(
                    "select count(*) from pg_stat_activity "
                    "where datname = current_database() and wait_event_type = 'Lock'"
                )
            )
            if waiting:
                break
            time.sleep(0.05)
        outcome["b_blocked_before_a_committed"] = bool(waiting)
    a.commit()
    a.close()
    thread.join(timeout=20)
    assert not thread.is_alive()

    print("\nPROBE RESULT:", outcome)
    assert str(outcome["b"]).startswith(("IntegrityError", "StaleVersionError"))
    with Session(committed_engine) as check:
        rows = check.scalars(select(AnalysisFindingReview)).all()
        assert [(r.status, r.version) for r in rows] == [("accepted", 1)]
        assert (
            check.scalar(select(func.count()).select_from(AnalysisFindingReviewEvent))
            == 1
        )
