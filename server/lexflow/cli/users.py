"""Manage sign-in accounts from the command line.

    python -m lexflow.cli.users create --email E --name N --role Administrator
    python -m lexflow.cli.users create --email E --name N --role Client --client-id UUID
    python -m lexflow.cli.users set-password --email E [--temporary]
    python -m lexflow.cli.users unlock --email E
    python -m lexflow.cli.users disable --email E
    python -m lexflow.cli.users enable --email E
    python -m lexflow.cli.users list

This is how the first Administrator is created; there is no self-registration.
Passwords are read from a masked prompt that shows one ``*`` per character
(asked twice; see ``lexflow.cli.masked_input``) or, for scripts, from standard
input with ``--password-stdin``. They are never accepted as a command
argument (arguments are visible to other users of the computer and stay in the
shell history), and never printed or logged. Each change is recorded in the
audit log as made from the command line by the current operating-system user.
"""

from __future__ import annotations

import argparse
import getpass
import sys
import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import TextIO

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from lexflow.audit import Actor, AuditLog
from lexflow.auth import passwords, sessions
from lexflow.auth.service import find_user_by_email, set_password
from lexflow.cli.masked_input import prompt_password
from lexflow.config import Settings, get_settings
from lexflow.db import engine_for, get_independent_sessions
from lexflow.domain import CLIENT, USER_ROLES
from lexflow.models import Client, User


class CommandError(Exception):
    """A problem to report to the operator (exit status 1)."""


class Console:
    """Where the command reads secrets from and writes messages to."""

    def __init__(
        self,
        *,
        stdin: TextIO = sys.stdin,
        stdout: TextIO = sys.stdout,
        prompt: Callable[[str], str] = prompt_password,
    ) -> None:
        self.stdin, self.stdout, self.prompt = stdin, stdout, prompt

    def say(self, message: str) -> None:
        print(message, file=self.stdout)


def _read_password(args: argparse.Namespace, console: Console) -> str:
    if args.password_stdin:
        line = console.stdin.readline()
        return line[:-1] if line.endswith("\n") else line
    first = console.prompt("New password: ")
    second = console.prompt("Repeat the new password: ")
    if first != second:
        raise CommandError("The two passwords do not match. Nothing was changed.")
    return first


def _checked_password(args: argparse.Namespace, console: Console, user: User) -> str:
    password = _read_password(args, console)
    problems = passwords.password_problems(password, email=user.email, name=user.name)
    if problems:
        raise CommandError("Password not accepted: " + " ".join(problems))
    return password


def _user(session: Session, email: str) -> User:
    user = find_user_by_email(session, email)
    if user is None:
        raise CommandError(f"No account with the e-mail address {email.strip()}.")
    return user


def _audit(settings: Settings, action: str, user: User, details: dict[str, str]) -> None:
    log = AuditLog(get_independent_sessions(engine_for(settings.database_url)))
    log.record(
        action,
        actor=Actor.command_line(getpass.getuser()),
        target_type="user",
        target_id=user.id,
        details={"email": user.email or "", "role": user.role, **details},
    )


def cmd_create(args: argparse.Namespace, session: Session, settings: Settings, c: Console) -> str:
    email = args.email.strip()
    name = args.name.strip()
    if not name:
        raise CommandError("A name is required.")
    if "@" not in email:
        raise CommandError("Enter a valid e-mail address.")
    if find_user_by_email(session, email) is not None:
        raise CommandError(f"An account with the e-mail address {email} already exists.")
    client_id: uuid.UUID | None = None
    if args.role == CLIENT:
        if not args.client_id:
            raise CommandError("A Client account needs --client-id (the client it represents).")
        try:
            client_id = uuid.UUID(args.client_id)
        except ValueError:
            raise CommandError("--client-id is not a valid id.") from None
        if session.get(Client, client_id) is None:
            raise CommandError("No client with that id exists.")
    elif args.client_id:
        raise CommandError("Only Client accounts represent a client; drop --client-id.")

    user = User(name=name, email=email, role=args.role, client_id=client_id)
    password = _checked_password(args, c, user)
    session.add(user)
    session.flush()
    now = datetime.now(UTC)
    set_password(session, user, password, now=now, settings=settings, temporary=args.temporary)
    session.commit()
    _audit(settings, "user.created", user, {"via": "command line"})
    note = " They must choose a new password at first sign-in." if args.temporary else ""
    return f"Created {user.role} account {user.email} ({user.id}).{note}"


def cmd_set_password(
    args: argparse.Namespace, session: Session, settings: Settings, c: Console
) -> str:
    user = _user(session, args.email)
    password = _checked_password(args, c, user)
    set_password(
        session, user, password, now=datetime.now(UTC), settings=settings, temporary=args.temporary
    )
    session.commit()
    _audit(settings, "user.password_set", user, {"temporary": str(args.temporary).lower()})
    note = " It must be changed at the next sign-in." if args.temporary else ""
    return f"Password set for {user.email}; their other sessions have ended.{note}"


def cmd_unlock(args: argparse.Namespace, session: Session, settings: Settings, c: Console) -> str:
    user = _user(session, args.email)
    user.failed_login_count, user.locked_until = 0, None
    session.commit()
    _audit(settings, "user.unlocked", user, {})
    return f"Unlocked {user.email}."


def _set_active(session: Session, settings: Settings, email: str, active: bool) -> str:
    user = _user(session, email)
    user.is_active = active
    if not active:
        sessions.revoke_all(session, user.id, datetime.now(UTC))
    session.commit()
    _audit(settings, "user.enabled" if active else "user.disabled", user, {})
    return f"{'Enabled' if active else 'Disabled'} {user.email}."


def cmd_disable(args: argparse.Namespace, session: Session, settings: Settings, c: Console) -> str:
    return _set_active(session, settings, args.email, active=False)


def cmd_enable(args: argparse.Namespace, session: Session, settings: Settings, c: Console) -> str:
    return _set_active(session, settings, args.email, active=True)


def cmd_list(args: argparse.Namespace, session: Session, settings: Settings, c: Console) -> str:
    now = datetime.now(UTC)
    rows = session.scalars(select(User).order_by(User.role, User.name)).all()
    lines = [f"{'E-MAIL':36} {'ROLE':14} {'SIGN-IN':10} NAME"]
    for user in rows:
        if not user.is_active:
            state = "disabled"
        elif user.locked_until is not None and user.locked_until > now:
            state = "locked"
        elif user.password_hash is None:
            state = "no password"
        else:
            state = "yes"
        sample = " (sample)" if user.is_sample else ""
        lines.append(f"{user.email or '-':36} {user.role:14} {state:10} {user.name}{sample}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m lexflow.cli.users", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    def with_password(sub: argparse.ArgumentParser) -> None:
        sub.add_argument(
            "--password-stdin",
            action="store_true",
            help="read the password from standard input (one line) instead of a prompt",
        )
        sub.add_argument(
            "--temporary",
            action="store_true",
            help="the user must replace it at the next sign-in; it expires after "
            "LEXFLOW_TEMPORARY_PASSWORD_HOURS",
        )

    create = commands.add_parser("create", help="create an account")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--role", required=True, choices=USER_ROLES)
    create.add_argument("--client-id", help="for Client accounts: the client they represent")
    with_password(create)
    create.set_defaults(handler=cmd_create)

    set_pw = commands.add_parser("set-password", help="set a password (also unlocks)")
    set_pw.add_argument("--email", required=True)
    with_password(set_pw)
    set_pw.set_defaults(handler=cmd_set_password)

    for name, handler, text in (
        ("unlock", cmd_unlock, "clear a lockout after failed sign-ins"),
        ("disable", cmd_disable, "stop an account from signing in and end its sessions"),
        ("enable", cmd_enable, "allow a disabled account to sign in again"),
    ):
        sub = commands.add_parser(name, help=text)
        sub.add_argument("--email", required=True)
        sub.set_defaults(handler=handler)

    listing = commands.add_parser("list", help="list accounts (no secrets)")
    listing.set_defaults(handler=cmd_list)
    return parser


def main(argv: Sequence[str] | None = None, console: Console | None = None) -> int:
    console = console or Console()
    args = build_parser().parse_args(argv)
    settings = get_settings()
    try:
        with Session(engine_for(settings.database_url), expire_on_commit=False) as session:
            console.say(args.handler(args, session, settings, console))
    except CommandError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        # Ctrl+C or Ctrl+D at a prompt: nothing has been saved yet (changes are
        # committed only after both passwords are read and accepted).
        print("Cancelled. Nothing was changed.", file=sys.stderr)
        return 130
    except DBAPIError:
        print(
            "The database could not be used: is it running, and are the migrations "
            "applied (alembic upgrade head)?",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
