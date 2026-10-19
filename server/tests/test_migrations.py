"""The migrations must build the schema the models describe, and undo it cleanly."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import URL, create_engine, inspect

from tests.conftest import (
    alembic_config,
    database_url,
    drop_database,
    recreate_database,
    run_alembic,
)

APP_TABLES = {
    "users",
    "clients",
    "cases",
    "hearings",
    "timeline_events",
    "documents",
    "case_number_counters",
}


@pytest.fixture
def scratch_url() -> Iterator[URL]:
    """A separate, empty database so this test can't disturb the shared one."""
    url = database_url("lexflow_migration_test")
    recreate_database(url)
    yield url
    drop_database(url)


def _tables(url: URL) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_then_downgrade_round_trip(scratch_url: URL) -> None:
    assert _tables(scratch_url) == set()

    run_alembic(scratch_url, ("upgrade", "head"))
    assert _tables(scratch_url) == APP_TABLES | {"alembic_version"}

    run_alembic(scratch_url, ("downgrade", "base"))
    assert _tables(scratch_url) == {"alembic_version"}

    # And forward again, as a fresh environment would.
    run_alembic(scratch_url, ("upgrade", "head"))
    assert _tables(scratch_url) >= APP_TABLES


def test_models_match_migrations(scratch_url: URL) -> None:
    """Fails if a model changed without a matching migration."""
    from alembic import command

    run_alembic(scratch_url, ("upgrade", "head"))
    command.check(alembic_config(scratch_url))  # raises if autogenerate finds a change
