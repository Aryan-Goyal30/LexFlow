"""Prepare and run an isolated API for the Playwright end-to-end tests.

    python scripts/e2e.py prepare   recreate the e2e database, migrate it, load sample data,
                                    and create the e2e sign-in accounts
    python scripts/e2e.py serve     run the API against that database on 127.0.0.1:8001
                                    (the harness adds --run-id HEX32 to mark its process)

The e2e database is the server named by ``DATABASE_URL`` with the database name
replaced by ``lexflow_e2e`` (override with ``LEXFLOW_E2E_DATABASE``; the name must
contain "e2e", because ``prepare`` drops it). Uploads go to
``server/var/e2e-uploads``, which ``prepare`` empties. The development database
and upload folder are never touched, and the database URL is never printed.

Sign-in accounts: when ``LEXFLOW_E2E_PASSWORD`` is set (the Playwright setup
generates a random one for each run and passes it in the environment, never on
the command line), ``prepare`` gives each account in ``E2E_ACCOUNTS`` that
password. The password is never printed. ``e2e/support/accounts.ts`` lists the
same accounts.
"""

from __future__ import annotations

import json
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
DEFAULT_APP_PORT = "5174"
RUN_ID = re.compile(r"[0-9a-f]{32}")

# (e-mail, name, role). Existing users (sample advocates) only get the password.
E2E_ACCOUNTS: list[tuple[str, str, str]] = [
    ("e2e.admin@lexflow.test", "E2E Administrator", "Administrator"),
    ("aryan.goyal@lexflow.test", "Aryan Goyal", "Advocate"),  # sample lead advocate
    ("e2e.lockout@lexflow.test", "E2E Lockout Check", "Advocate"),
    ("e2e.paralegal@lexflow.test", "E2E Paralegal", "Paralegal"),
    ("rajat.deshpande@lexflow.test", "Rajat Deshpande", "Advocate"),  # leads another case
    ("e2e.client@client.example", "E2E Client Contact", "Client"),  # the Sattvik case's client
]
# Client accounts: which sample client each represents.
E2E_CLIENT_OF = {"e2e.client@client.example": "c-005"}
# (e-mail, sample case, member role): case teams for the e2e accounts.
E2E_MEMBERS: list[tuple[str, str, str]] = [
    ("e2e.paralegal@lexflow.test", "case-1005", "paralegal"),
]

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
        accounts = _create_accounts(session, os.environ.get("LEXFLOW_E2E_PASSWORD"))
    engine.dispose()

    shutil.rmtree(UPLOAD_DIR, ignore_errors=True)
    UPLOAD_DIR.mkdir(parents=True)
    print(
        f"e2e database {url.database!r} ready: {result.total} sample rows, "
        f"{accounts} sign-in accounts."
    )
    return 0


def _create_accounts(session: Session, password: str | None) -> int:
    from datetime import UTC, datetime

    from sqlalchemy import func, select

    from lexflow.auth.service import set_password
    from lexflow.models import CaseMember, User
    from lexflow.seed import sample_uuid

    if not password:
        return 0
    if len(password) < 12:
        raise SystemExit("LEXFLOW_E2E_PASSWORD must have at least 12 characters.")
    settings = Settings()  # DATABASE_URL from the environment or .env
    now = datetime.now(UTC)
    for email, name, role in E2E_ACCOUNTS:
        user = session.scalar(select(User).where(func.lower(User.email) == email))
        if user is None:
            client_id = sample_uuid("client", E2E_CLIENT_OF[email]) if role == "Client" else None
            user = User(name=name, email=email, role=role, client_id=client_id)
            session.add(user)
            session.flush()
        set_password(session, user, password, now=now, settings=settings, temporary=False)
    session.flush()
    for email, legacy_case, member_role in E2E_MEMBERS:
        member = session.scalar(select(User).where(func.lower(User.email) == email))
        if member is not None:
            session.add(
                CaseMember(
                    case_id=sample_uuid("case", legacy_case),
                    user_id=member.id,
                    member_role=member_role,
                )
            )
    return len(E2E_ACCOUNTS)


def serve() -> int:
    url = e2e_database_url()
    os.environ["DATABASE_URL"] = url.render_as_string(hide_password=False)
    os.environ["LEXFLOW_UPLOAD_DIR"] = str(UPLOAD_DIR)
    os.environ["LEXFLOW_API_HOST"] = "127.0.0.1"
    os.environ["LEXFLOW_API_PORT"] = os.environ.get("LEXFLOW_E2E_API_PORT", DEFAULT_PORT)
    os.environ["LEXFLOW_ENV"] = "development"
    # The e2e app (Vite on its own port) is the only origin allowed to make changes.
    app_port = os.environ.get("LEXFLOW_E2E_APP_PORT", DEFAULT_APP_PORT)
    os.environ["LEXFLOW_ALLOWED_ORIGINS"] = json.dumps(
        [f"http://localhost:{app_port}", f"http://127.0.0.1:{app_port}"]
    )
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
