"""Signing in, signing out and changing a password.

Every refused sign-in gets the same answer (401, "Email or password is
incorrect.") and takes about as long, whether the account is unknown, locked,
deactivated, not yet allowed to sign in, or the password is wrong. The real
reason goes only to the audit log.

Lockout: the ``login_max_failures``-th consecutive wrong password (5 by default)
locks the account for ``lockout_minutes`` (15). While locked, even the correct
password is refused, and further attempts neither count nor extend the lock. A
successful sign-in resets the count; an expired lock starts the count afresh.
Failure counts and the audit entries are written through an independent
session, so they are kept although the request fails.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lexflow.audit import Actor, AuditLog
from lexflow.auth import passwords, sessions
from lexflow.config import Settings
from lexflow.db import IndependentSessions
from lexflow.domain import ADMINISTRATOR, ADVOCATE, CLIENT, PARALEGAL
from lexflow.errors import FieldError, ProblemError
from lexflow.models import User, UserSession

INVALID_CREDENTIALS = "Email or password is incorrect."

# Roles that may sign in. A role is added only once the server enforces what it
# may see and do: Paralegals since assignment scoping (lexflow.authz); Clients
# since the client portal (lexflow.services.portal), whose isolation from the
# staff routes is tested in tests/test_portal.py.
SIGN_IN_ROLES: frozenset[str] = frozenset({ADMINISTRATOR, ADVOCATE, PARALEGAL, CLIENT})


def invalid_credentials() -> ProblemError:
    return ProblemError(401, "invalid-credentials", INVALID_CREDENTIALS, title="Sign-in failed")


@dataclass
class SignedIn:
    user: User
    token: str


def find_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))


def _refusal_reason(user: User, now: datetime) -> str | None:
    """Why this account cannot sign in right now, before checking the password."""
    if user.locked_until is not None and user.locked_until > now:
        return "locked"
    if not user.is_active:
        return "inactive"
    if user.role not in SIGN_IN_ROLES:
        return "role-not-enabled"
    if user.password_hash is None:
        return "no-password"
    return None


def _record_failure(
    independent: IndependentSessions,
    audit: AuditLog,
    user: User,
    *,
    now: datetime,
    settings: Settings,
    action: str,
) -> None:
    """Count a wrong password (locking the account at the limit), independently."""
    with independent() as side:
        row = side.get(User, user.id, with_for_update=True, populate_existing=True)
        if row is None:  # deleted meanwhile
            return
        if row.locked_until is not None and row.locked_until <= now:
            row.failed_login_count, row.locked_until = 0, None  # the old lock is over
        row.failed_login_count += 1
        locked = row.failed_login_count >= settings.login_max_failures
        if locked and row.locked_until is None:
            row.locked_until = now + timedelta(minutes=settings.lockout_minutes)
        failures = row.failed_login_count
    audit.record(
        action,
        actor=user,
        outcome="failed",
        target_type="user",
        target_id=user.id,
        details={"reason": "wrong-password", "consecutiveFailures": failures, "locked": locked},
    )


def sign_in(
    session: Session,
    independent: IndependentSessions,
    audit: AuditLog,
    *,
    email: str,
    password: str,
    now: datetime,
    settings: Settings,
    user_agent: str | None,
    previous_token: str | None,
) -> SignedIn:
    profile = settings.password_hash_profile
    user = find_user_by_email(session, email)
    if user is None:
        passwords.burn_verification_time(password, profile)
        # The submitted address is not recorded: people sometimes type a
        # password into the e-mail field.
        audit.record(
            "auth.sign_in", actor=None, outcome="failed", details={"reason": "unknown-account"}
        )
        raise invalid_credentials()

    reason = _refusal_reason(user, now)
    if reason is not None:
        passwords.burn_verification_time(password, profile)
        audit.record(
            "auth.sign_in",
            actor=user,
            outcome="failed",
            target_type="user",
            target_id=user.id,
            details={"reason": reason},
        )
        raise invalid_credentials()

    stored_hash = user.password_hash
    if stored_hash is None or not passwords.verify_password(stored_hash, password, profile):
        _record_failure(independent, audit, user, now=now, settings=settings, action="auth.sign_in")
        raise invalid_credentials()

    if (
        user.must_change_password
        and user.temp_password_expires_at is not None
        and user.temp_password_expires_at <= now
    ):
        audit.record(
            "auth.sign_in",
            actor=user,
            outcome="failed",
            target_type="user",
            target_id=user.id,
            details={"reason": "temporary-password-expired"},
        )
        raise invalid_credentials()

    # Success. A session presented with the sign-in is ended (no fixation).
    if previous_token is not None:
        found = sessions.find(session, previous_token, now=now, settings=settings)
        if found is not None:
            sessions.revoke(found[0], now)
    user.failed_login_count, user.locked_until, user.last_login_at = 0, None, now
    if passwords.needs_rehash(stored_hash, profile):
        user.password_hash = passwords.hash_password(password, profile)
    sessions.purge_stale(session, now)
    token = sessions.start(session, user, now=now, settings=settings, user_agent=user_agent)
    session.commit()
    audit.record("auth.sign_in", actor=user, target_type="user", target_id=user.id)
    return SignedIn(user=user, token=token)


def sign_out(
    session: Session, audit: AuditLog, *, token: str | None, now: datetime, settings: Settings
) -> None:
    found = sessions.find(session, token, now=now, settings=settings)
    if found is None:
        return
    live, user = found
    sessions.revoke(live, now)
    session.commit()
    audit.record("auth.sign_out", actor=user, target_type="user", target_id=user.id)


def set_password(
    session: Session,
    user: User,
    new_password: str,
    *,
    now: datetime,
    settings: Settings,
    temporary: bool,
) -> None:
    """Store a new password and end the user's sessions. The caller commits.

    A temporary password (set by an administrator) must be changed at the next
    sign-in and stops working after ``temporary_password_hours``.
    """
    user.password_hash = passwords.hash_password(new_password, settings.password_hash_profile)
    user.must_change_password = temporary
    user.temp_password_expires_at = (
        now + timedelta(hours=settings.temporary_password_hours) if temporary else None
    )
    user.failed_login_count, user.locked_until = 0, None
    sessions.revoke_all(session, user.id, now)


def change_own_password(
    session: Session,
    independent: IndependentSessions,
    audit: AuditLog,
    *,
    user: User,
    live: UserSession,
    current_password: str,
    new_password: str,
    now: datetime,
    settings: Settings,
    user_agent: str | None,
) -> str:
    """Change the signed-in user's password; returns a new session token.

    The current password is required (a stolen session alone cannot take over
    the account) and a wrong one counts towards the lockout. Every other session
    of the user ends.
    """
    stored_hash = user.password_hash
    if stored_hash is None or not passwords.verify_password(
        stored_hash, current_password, settings.password_hash_profile
    ):
        _record_failure(
            independent, audit, user, now=now, settings=settings, action="auth.password_change"
        )
        raise ProblemError(
            422,
            "validation-error",
            "Correct the highlighted fields and try again.",
            title="Some fields are invalid",
            errors=[
                FieldError(field="currentPassword", message="Your current password is incorrect.")
            ],
        )
    problems = passwords.password_problems(new_password, email=user.email, name=user.name)
    if passwords.verify_password(stored_hash, new_password, settings.password_hash_profile):
        problems.append("Choose a password different from your current one.")
    if problems:
        raise ProblemError(
            422,
            "validation-error",
            "Correct the highlighted fields and try again.",
            title="Some fields are invalid",
            errors=[FieldError(field="newPassword", message=" ".join(problems))],
        )
    set_password(session, user, new_password, now=now, settings=settings, temporary=False)
    sessions.revoke(live, now)
    token = sessions.start(session, user, now=now, settings=settings, user_agent=user_agent)
    session.commit()
    audit.record("auth.password_change", actor=user, target_type="user", target_id=user.id)
    return token


def record_cli_event(audit: AuditLog, action: str, operator: str, user: User) -> None:
    audit.record(
        action,
        actor=Actor.command_line(operator),
        target_type="user",
        target_id=user.id,
        details={"email": user.email, "role": user.role},
    )
