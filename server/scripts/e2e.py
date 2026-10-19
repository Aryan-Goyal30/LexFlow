"""Prepare and run an isolated API for the Playwright end-to-end tests.

    python scripts/e2e.py prepare   recreate the e2e database, migrate it, load sample data
    python scripts/e2e.py serve     run the API against that database on 127.0.0.1:8001
                                    (the harness adds --run-id HEX32 to mark its process)

The e2e database is the server named by ``DATABASE_URL`` with the database name
replaced by ``lexflow_e2e`` (override with ``LEXFLOW_E2E_DATABASE``; the name must
contain "e2e", because ``prepare`` drops it). Uploads go to
``server/var/e2e-uploads``, which ``prepare`` empties. The development database
and upload folder are never touched, and the database URL is never printed.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

from sqlalchemy import URL, create_engine, make_url, text
from sqlalchemy.orm import Session

SERVER_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = SERVER_ROOT / "var" / "e2e-uploads"
DEFAULT_PORT = "8001"
RUN_ID = re.compile(r"[0-9a-f]{32}")

sys.path.insert(0, str(SERVER_ROOT))

from lexflow.config import Settings, get_settings  # noqa: E402 - needs the path above


def e2e_database_url() -> URL:
    name = os.environ.get("LEXFLOW_E2E_DATABASE", "lexflow_e2e")
    if "e2e" not in name:
        raise SystemExit(f"Refusing to use database {name!r}: its name must contain 'e2e'.")
    base = make_url(Settings().database_url)  # DATABASE_URL from the environment or .env
    return base.set(database=name)


def prepare() -> int:
    from alembic import command
    from alembic.config import Config

    from lexflow.db import engine_for
    from lexflow.seed.loader import load_sample_data

    url = e2e_database_url()
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        connection.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()

    config = Config(str(SERVER_ROOT / "alembic.ini"))
    config.attributes["database_url"] = url.render_as_string(hide_password=False)
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")

    engine = engine_for(url.render_as_string(hide_password=False))
    with Session(engine) as session, session.begin():
        result = load_sample_data(session)
    engine.dispose()

    shutil.rmtree(UPLOAD_DIR, ignore_errors=True)
    UPLOAD_DIR.mkdir(parents=True)
    print(f"e2e database {url.database!r} ready: {result.total} sample rows loaded.")
    return 0


def serve() -> int:
    url = e2e_database_url()
    os.environ["DATABASE_URL"] = url.render_as_string(hide_password=False)
    os.environ["LEXFLOW_UPLOAD_DIR"] = str(UPLOAD_DIR)
    os.environ["LEXFLOW_API_HOST"] = "127.0.0.1"
    os.environ["LEXFLOW_API_PORT"] = os.environ.get("LEXFLOW_E2E_API_PORT", DEFAULT_PORT)
    os.environ["LEXFLOW_ENV"] = "development"
    get_settings.cache_clear()

    from lexflow.__main__ import main as run_api

    return run_api()


def main() -> int:
    args = sys.argv[1:]
    if args == ["prepare"]:
        return prepare()
    # The optional run id only marks the process: the test harness checks that a
    # process's command line carries its run id before it ever stops it.
    if args == ["serve"] or (
        len(args) == 3 and args[:2] == ["serve", "--run-id"] and RUN_ID.fullmatch(args[2])
    ):
        return serve()
    print("usage: python scripts/e2e.py prepare | serve [--run-id HEX32]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
