"""The sample-data loader: faithful to the source, repeat-safe, development only."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import URL, create_engine, func, select
from sqlalchemy.orm import Session

from lexflow.models import Case, CaseNumberCounter, Client, Document, Hearing, TimelineEvent, User
from lexflow.seed import sample_uuid
from lexflow.seed.loader import load_sample_data, read_sample_data, sample_row_counts
from tests.conftest import (
    SERVER_ROOT,
    database_url,
    drop_database,
    recreate_database,
    run_alembic,
)

DATA = read_sample_data()


def _expected_counts(data: dict[str, Any]) -> dict[str, int]:
    return {
        "users": len(data["advocates"]),
        "clients": len(data["clients"]),
        "cases": len(data["cases"]),
        "hearings": sum(len(c["hearings"]) for c in data["cases"]),
        "timeline_events": sum(len(c["timeline"]) for c in data["cases"]),
        "documents": sum(len(c["documents"]) for c in data["cases"]),
    }


def test_sample_data_file_matches_known_shape() -> None:
    # Guards against an accidentally truncated export.
    assert _expected_counts(DATA) == {
        "users": 5,
        "clients": 6,
        "cases": 6,
        "hearings": 5,
        "timeline_events": 22,
        "documents": 26,
    }


def test_loads_every_record_as_sample(db: Session) -> None:
    result = load_sample_data(db)

    assert result.inserted == _expected_counts(DATA)
    assert sample_row_counts(db) == _expected_counts(DATA)
    for model in (User, Client, Case, Hearing, TimelineEvent, Document):
        not_sample = db.scalar(
            select(func.count()).select_from(model).where(model.is_sample.is_(False))
        )
        assert not_sample == 0, model.__tablename__


def test_second_load_adds_nothing(db: Session) -> None:
    load_sample_data(db)
    second = load_sample_data(db)

    assert second.total == 0
    assert sample_row_counts(db) == _expected_counts(DATA)


def test_ids_are_stable_and_relationships_preserved(db: Session) -> None:
    load_sample_data(db)

    for source in DATA["cases"]:
        case = db.get(Case, sample_uuid("case", source["legacyId"]))
        assert case is not None, source["legacyId"]
        client = db.get(Client, case.client_id)
        advocate = db.get(User, case.lead_advocate_id)
        assert client is not None and client.name == source["clientName"]
        assert advocate is not None and advocate.name == source["leadAdvocate"]
        assert case.case_number == source["caseNumber"]
        assert case.title == source["title"]
        assert case.description == source["description"]
        assert case.opened_on.isoformat() == source["openedOn"]
        assert (case.court_name, case.opposing_party) == (
            source["courtName"],
            source["opposingParty"],
        )

        hearing_dates = sorted(
            h.hearing_date.isoformat()
            for h in db.scalars(select(Hearing).where(Hearing.case_id == case.id))
        )
        assert hearing_dates == sorted(h["date"] for h in source["hearings"])
        event_labels = [
            e.label
            for e in db.scalars(
                select(TimelineEvent)
                .where(TimelineEvent.case_id == case.id)
                .order_by(TimelineEvent.event_date)
            )
        ]
        assert event_labels == [t["label"] for t in source["timeline"]]


def test_sample_documents_have_no_file_and_keep_their_label(db: Session) -> None:
    load_sample_data(db)

    documents = db.scalars(select(Document)).all()
    assert documents
    for document in documents:
        assert document.storage_key is None
        assert document.sha256 is None
        assert document.size_bytes is None  # never a made-up measurement
        assert document.size_label
        assert not document.has_file


def test_case_number_counters_start_above_sample_numbers(db: Session) -> None:
    load_sample_data(db)

    counters = {c.year: c.last_value for c in db.scalars(select(CaseNumberCounter))}
    assert counters == {2025: 331, 2026: 489}


def test_existing_higher_counter_is_kept(db: Session) -> None:
    db.add(CaseNumberCounter(year=2026, last_value=900))
    db.flush()
    load_sample_data(db)

    assert db.get(CaseNumberCounter, 2026).last_value == 900  # type: ignore[union-attr]


# --- the command line entry point -------------------------------------------


@pytest.fixture
def seed_database() -> Iterator[URL]:
    url = database_url("lexflow_seed_test")
    recreate_database(url)
    run_alembic(url, ("upgrade", "head"))
    yield url
    drop_database(url)


def _run_seed(url: URL, env: str) -> subprocess.CompletedProcess[str]:
    rendered = url.render_as_string(hide_password=False)
    environment = {**os.environ, "DATABASE_URL": rendered, "LEXFLOW_ENV": env}
    return subprocess.run(
        [sys.executable, "-m", "lexflow.seed"],
        cwd=SERVER_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _case_count(url: URL) -> int:
    engine = create_engine(url)
    try:
        with Session(engine) as session:
            return session.scalar(select(func.count()).select_from(Case)) or 0
    finally:
        engine.dispose()


@pytest.mark.parametrize("env", ["production", "test"])
def test_command_refuses_outside_development(seed_database: URL, env: str) -> None:
    result = _run_seed(seed_database, env)

    assert result.returncode == 2
    assert "LEXFLOW_ENV=development" in result.stderr
    assert _case_count(seed_database) == 0


def test_command_loads_once_in_development(seed_database: URL) -> None:
    first = _run_seed(seed_database, "development")
    assert first.returncode == 0, first.stderr
    assert "Loaded fictional sample data" in first.stdout
    assert _case_count(seed_database) == len(DATA["cases"])

    second = _run_seed(seed_database, "development")
    assert second.returncode == 0, second.stderr
    assert "already loaded" in second.stdout
    assert _case_count(seed_database) == len(DATA["cases"])
