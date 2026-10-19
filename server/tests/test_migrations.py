"""The migrations must build the schema the models describe, and undo it cleanly."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import URL, create_engine, func, inspect, select, table, text
from sqlalchemy.exc import DBAPIError, IntegrityError

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
    "sessions",
    "audit_events",
    "case_members",
    "document_extractions",
    "document_sections",
    "document_chunks",
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


# --- upgrading a database that already holds data ------------------------------

PHASE1_ROWS = """
INSERT INTO clients (id, name, email, phone, is_sample)
VALUES ('00000000-0000-4000-8000-0000000000c1', 'Example Client', 'contact@client.example',
        '+91 00000 00000', false);
INSERT INTO users (id, name, email, role, is_sample)
VALUES ('00000000-0000-4000-8000-0000000000a1', 'Example Advocate', NULL, 'Advocate', false),
       ('00000000-0000-4000-8000-0000000000a2', 'Example Paralegal', NULL, 'Paralegal', false);
INSERT INTO cases (id, case_number, title, status, priority, practice_area, client_id,
                   lead_advocate_id, description, opened_on)
VALUES ('00000000-0000-4000-8000-0000000000e1', 'LF-2026-0001', 'Example v. Example', 'Open',
        'Medium', 'Civil', '00000000-0000-4000-8000-0000000000c1',
        '00000000-0000-4000-8000-0000000000a1', 'A matter that existed before Phase 2.',
        '2026-01-05');
INSERT INTO hearings (id, case_id, hearing_date, court, purpose)
VALUES ('00000000-0000-4000-8000-0000000000b1', '00000000-0000-4000-8000-0000000000e1',
        '2026-02-01', 'Court', 'Listing');
INSERT INTO timeline_events (id, case_id, event_date, label, description)
VALUES ('00000000-0000-4000-8000-0000000000d1', '00000000-0000-4000-8000-0000000000e1',
        '2026-01-05', 'Matter opened', 'Created.');
INSERT INTO documents (id, case_id, name, document_type, size_label, uploaded_on)
VALUES ('00000000-0000-4000-8000-0000000000f1', '00000000-0000-4000-8000-0000000000e1',
        'Plaint.pdf', 'PDF', '1 KB', '2026-01-05');
"""

COUNTED = ("clients", "users", "cases", "hearings", "timeline_events", "documents")


def _counts(url: URL) -> dict[str, int]:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return {
                name: connection.execute(select(func.count()).select_from(table(name))).scalar_one()
                for name in COUNTED
            }
    finally:
        engine.dispose()


def test_existing_data_survives_upgrade_and_downgrade(scratch_url: URL) -> None:
    run_alembic(scratch_url, ("upgrade", "0001"))
    engine = create_engine(scratch_url)
    with engine.begin() as connection:
        connection.execute(text(PHASE1_ROWS))
    engine.dispose()
    before = _counts(scratch_url)
    assert all(before.values())

    run_alembic(scratch_url, ("upgrade", "head"))
    assert _counts(scratch_url) == before
    engine = create_engine(scratch_url)
    with engine.connect() as connection:
        users = connection.execute(
            text(
                "SELECT role, is_active, must_change_password, failed_login_count, "
                "password_hash, client_id FROM users ORDER BY role"
            )
        ).all()
    engine.dispose()
    # Existing people stay active, cannot sign in yet, and represent no client.
    assert [tuple(u) for u in users] == [
        ("Advocate", True, False, 0, None, None),
        ("Paralegal", True, False, 0, None, None),
    ]

    run_alembic(scratch_url, ("downgrade", "0001"))
    assert _counts(scratch_url) == before


def test_soft_deleted_names_may_repeat_and_downgrade_refuses_to_lose_them(
    scratch_url: URL,
) -> None:
    run_alembic(scratch_url, ("upgrade", "0001"))
    engine = create_engine(scratch_url)
    with engine.begin() as connection:
        connection.execute(text(PHASE1_ROWS))
    # After 0005 a deleted document may share its name with a live one.
    run_alembic(scratch_url, ("upgrade", "0005"))
    copy = (
        "INSERT INTO documents (id, case_id, name, document_type, size_label, uploaded_on, "
        "deleted_at) SELECT '00000000-0000-4000-8000-0000000000d9', case_id, upper(name), "
        "document_type, size_label, uploaded_on, {deleted} FROM documents LIMIT 1"
    )
    with engine.begin() as connection:
        connection.execute(text(copy.format(deleted="now()")))
    # ...but two live ones may not.
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(copy.format(deleted="NULL").replace("0000000000d9", "0000000000da"))
        )

    # Going back to the old unique index would fail on the deleted copy: refused,
    # with nothing changed.
    with pytest.raises(DBAPIError, match="purge or rename them before downgrading"):
        run_alembic(scratch_url, ("downgrade", "0004"))
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert version == "0005"
        connection.execute(
            text("DELETE FROM documents WHERE id = '00000000-0000-4000-8000-0000000000d9'")
        )
        connection.commit()
    engine.dispose()
    run_alembic(scratch_url, ("downgrade", "0004"))


def test_existing_hearings_become_scheduled_and_downgrade_keeps_cancellations(
    scratch_url: URL,
) -> None:
    run_alembic(scratch_url, ("upgrade", "0005"))
    engine = create_engine(scratch_url)
    with engine.begin() as connection:
        connection.execute(text(PHASE1_ROWS))
    run_alembic(scratch_url, ("upgrade", "0006"))
    with engine.begin() as connection:
        statuses = connection.execute(text("SELECT DISTINCT status FROM hearings")).scalars()
        assert list(statuses) == ["Scheduled"]
        # The status and the cancellation time must agree.
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(text("UPDATE hearings SET status = 'Cancelled'"))
        connection.execute(text("UPDATE hearings SET status = 'Cancelled', cancelled_at = now()"))

    with pytest.raises(DBAPIError, match="cancelled hearings exist"):
        run_alembic(scratch_url, ("downgrade", "0005"))
    with engine.begin() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0006"
        )
        connection.execute(text("UPDATE hearings SET status = 'Scheduled', cancelled_at = NULL"))
    engine.dispose()
    run_alembic(scratch_url, ("downgrade", "0005"))
