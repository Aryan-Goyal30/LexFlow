"""The isolated demo database: is the database we are connected to really it?

Demo-only behaviour (marking a new client or case as fictional, so a whole
demonstration can run on a new case) must never be possible against the live
database. The settings already refuse ``LEXFLOW_DEMO_MODE`` unless the
configured URL names a test or e2e database. A name in a URL is not proof of
identity, so every request that relies on demo mode also checks the
connection itself, and fails closed:

1. demo mode is on;
2. ``current_database()``, asked of the live connection, is the database the
   URL names, and that name has a ``test`` or ``e2e`` part;
3. the database carries the marker comment ``DEMO_MARKER``.

The marker (``COMMENT ON DATABASE``, a catalog entry, not a table row) is
written only by ``scripts/e2e.py prepare`` when it creates the demo database,
and by the test suite on its own throwaway database. The live database is
never given it. Any error while checking counts as "not verified".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from lexflow.config import Settings, is_test_database_name

logger = logging.getLogger("lexflow.demo")

DEMO_MARKER = "lexflow:isolated-demo:v1"

OFF = "Demo mode is off on this server."
UNVERIFIED = (
    "This server is in demo mode, but the database it is connected to could not be verified "
    "as the isolated demo database, so fictional demo records cannot be created."
)


@dataclass(frozen=True)
class DemoStatus:
    enabled: bool  # LEXFLOW_DEMO_MODE
    verified: bool  # the connected database is the marked, isolated demo database
    reason: str | None  # why demo records cannot be created (safe for every staff member)


def status(session: Session, settings: Settings) -> DemoStatus:
    if not settings.demo_mode:
        return DemoStatus(False, False, OFF)
    try:
        configured = make_url(settings.database_url).database or ""
        connected, marker = session.execute(
            text(
                "SELECT current_database(), shobj_description(oid, 'pg_database') "
                "FROM pg_database WHERE datname = current_database()"
            )
        ).one()
    except Exception as error:  # fail closed: anything unexpected means "not verified"
        logger.warning("demo check failed (%s)", type(error).__name__)
        return DemoStatus(True, False, UNVERIFIED)
    verified = (
        connected == configured and is_test_database_name(connected) and marker == DEMO_MARKER
    )
    if not verified:
        logger.warning("demo mode is on but the connected database is not the marked demo one")
    return DemoStatus(True, verified, None if verified else UNVERIFIED)


def mark_statement(database: str) -> str:
    """The SQL that marks a freshly created database as the isolated demo one.
    Only for a name with a ``test`` or ``e2e`` part."""
    if not is_test_database_name(database) or '"' in database:
        raise ValueError(f"refusing to mark database {database!r} as a demo database")
    return f"COMMENT ON DATABASE \"{database}\" IS '{DEMO_MARKER}'"
