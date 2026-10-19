"""The account command line (``python -m lexflow.cli.users``).

The command opens its own database connection and commits, like an operator's
shell would, so these tests use ``committed_engine`` (cleaned up afterwards).
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from lexflow.auth.passwords import verify_password
from lexflow.auth.sessions import start
from lexflow.cli.users import Console, main
from lexflow.config import get_settings
from lexflow.models import AuditEvent, Client, User, UserSession
from tests.conftest import SERVER_ROOT, TEST_DATABASE_URL

PASSWORD = "an operator chosen passphrase"


class Run:
    def __init__(self) -> None:
        self.out = io.StringIO()

    def __call__(self, *argv: str, stdin: str = "", prompts: tuple[str, ...] = ()) -> int:
        answers = iter(prompts)
        console = Console(stdin=io.StringIO(stdin), stdout=self.out, prompt=lambda _: next(answers))
        return main(list(argv), console)


@pytest.fixture
def run(committed_engine: Engine) -> Iterator[Run]:
    yield Run()


def user(engine: Engine, email: str) -> User:
    with Session(engine) as session:
        found = session.scalar(select(User).where(User.email == email))
        assert found is not None
        session.expunge(found)
        return found


def test_create_an_administrator_with_a_hidden_prompt(
    run: Run, committed_engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    code = run(
        "create",
        "--email",
        "admin@lexflow.test",
        "--name",
        "First Admin",
        "--role",
        "Administrator",
        prompts=(PASSWORD, PASSWORD),
    )

    assert code == 0
    created = user(committed_engine, "admin@lexflow.test")
    assert created.role == "Administrator" and created.is_active
    assert created.password_hash is not None and created.password_hash.startswith("$argon2id$")
    assert verify_password(created.password_hash, PASSWORD, "test-fast")
    assert not created.must_change_password
    assert PASSWORD not in run.out.getvalue() + capsys.readouterr().err
    with Session(committed_engine) as session:
        event = session.scalars(select(AuditEvent).where(AuditEvent.action == "user.created")).one()
        assert event.actor_role == "Operator"
        assert (event.actor_name or "").startswith("command line (")


def test_mismatched_or_weak_passwords_create_nothing(
    run: Run, committed_engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    args = ("create", "--email", "a@lexflow.test", "--name", "A", "--role", "Advocate")
    assert run(*args, prompts=(PASSWORD, PASSWORD + "x")) == 1
    assert "do not match" in capsys.readouterr().err
    assert run(*args, "--password-stdin", stdin="short\n") == 1
    assert "at least 12" in capsys.readouterr().err
    with Session(committed_engine) as session:
        assert session.scalars(select(User)).all() == []


def test_passwords_are_never_accepted_as_an_argument(run: Run) -> None:
    with pytest.raises(SystemExit) as exit_info:
        run(
            "create",
            "--email",
            "a@lexflow.test",
            "--name",
            "A",
            "--role",
            "Advocate",
            "--password",
            PASSWORD,
        )
    assert exit_info.value.code == 2  # argparse: unknown option


def test_duplicate_addresses_and_client_links_are_checked(
    run: Run, committed_engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    stdin = PASSWORD + "\n"
    base = ("--name", "Someone", "--password-stdin")
    assert (
        run("create", "--email", "dup@lexflow.test", "--role", "Advocate", *base, stdin=stdin) == 0
    )
    assert (
        run("create", "--email", "DUP@lexflow.test", "--role", "Paralegal", *base, stdin=stdin) == 1
    )
    assert "already exists" in capsys.readouterr().err

    assert run("create", "--email", "c@client.example", "--role", "Client", *base, stdin=stdin) == 1
    assert "--client-id" in capsys.readouterr().err

    with Session(committed_engine) as session, session.begin():
        client = Client(name="Linked Client", email="x@client.example", phone="+91 0")
        session.add(client)
        session.flush()
        client_id = str(client.id)
    assert (
        run(
            "create",
            "--email",
            "s@lexflow.test",
            "--role",
            "Advocate",
            "--client-id",
            client_id,
            *base,
            stdin=stdin,
        )
        == 1
    )
    assert "Only Client accounts" in capsys.readouterr().err
    assert (
        run(
            "create",
            "--email",
            "c@client.example",
            "--role",
            "Client",
            "--client-id",
            client_id,
            *base,
            stdin=stdin,
        )
        == 0
    )
    assert user(committed_engine, "c@client.example").client_id is not None


def test_set_password_unlocks_ends_sessions_and_can_be_temporary(
    run: Run, committed_engine: Engine
) -> None:
    run(
        "create",
        "--email",
        "p@lexflow.test",
        "--name",
        "P",
        "--role",
        "Advocate",
        "--password-stdin",
        stdin=PASSWORD + "\n",
    )
    now = datetime.now(UTC)
    with Session(committed_engine) as session, session.begin():
        row = session.scalar(select(User).where(User.email == "p@lexflow.test"))
        assert row is not None
        row.failed_login_count, row.locked_until = 5, now + timedelta(minutes=10)
        start(session, row, now=now, settings=get_settings(), user_agent=None)

    assert (
        run(
            "set-password",
            "--email",
            "p@lexflow.test",
            "--temporary",
            "--password-stdin",
            stdin="a temporary passphrase\n",
        )
        == 0
    )

    updated = user(committed_engine, "p@lexflow.test")
    assert (updated.failed_login_count, updated.locked_until) == (0, None)
    assert updated.must_change_password and updated.temp_password_expires_at is not None
    with Session(committed_engine) as session:
        live = session.scalars(select(UserSession).where(UserSession.revoked_at.is_(None))).all()
        assert live == []


def test_unlock_disable_enable_and_list(
    run: Run, committed_engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    run(
        "create",
        "--email",
        "u@lexflow.test",
        "--name",
        "U Person",
        "--role",
        "Paralegal",
        "--password-stdin",
        stdin=PASSWORD + "\n",
    )
    assert run("disable", "--email", "u@lexflow.test") == 0
    assert not user(committed_engine, "u@lexflow.test").is_active
    assert run("enable", "--email", "u@lexflow.test") == 0
    assert run("unlock", "--email", "u@lexflow.test") == 0
    assert run("unlock", "--email", "nobody@lexflow.test") == 1
    assert "No account" in capsys.readouterr().err

    run.out = io.StringIO()
    assert run("list") == 0
    listing = run.out.getvalue()
    assert "u@lexflow.test" in listing and "Paralegal" in listing
    assert "$argon2" not in listing


def test_the_real_command_prints_no_secret(committed_engine: Engine) -> None:
    environment = {
        **os.environ,
        "DATABASE_URL": TEST_DATABASE_URL.render_as_string(hide_password=False),
        "LEXFLOW_ENV": "test",
    }
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "lexflow.cli.users",
            "create",
            "--email",
            "sub@lexflow.test",
            "--name",
            "Sub Process",
            "--role",
            "Advocate",
            "--password-stdin",
        ],
        cwd=SERVER_ROOT,
        env=environment,
        input=PASSWORD + "\n",
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Created Advocate account sub@lexflow.test" in result.stdout
    assert PASSWORD not in result.stdout + result.stderr
