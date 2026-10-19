"""Password hashing (Argon2id) and the password policy.

Hashes are PHC strings (``$argon2id$v=19$m=...``), so the parameters travel with
each hash and can be raised later: ``needs_rehash`` tells sign-in to upgrade an
old hash. Passwords themselves are never stored, logged or returned.

The "standard" profile uses argon2-cffi's defaults (the RFC 9106 low-memory
profile: 3 passes over 64 MiB, 4 lanes). The "test-fast" profile exists only to
keep the test suite quick; settings refuse it outside ``LEXFLOW_ENV=test``.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

Profile = Literal["standard", "test-fast"]

MIN_LENGTH = 12
MAX_LENGTH = 128


@lru_cache
def _hasher(profile: Profile) -> PasswordHasher:
    if profile == "test-fast":
        return PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    return PasswordHasher()  # argon2id, RFC 9106 low-memory parameters


def hash_password(password: str, profile: Profile) -> str:
    return _hasher(profile).hash(password)


def verify_password(stored_hash: str, password: str, profile: Profile) -> bool:
    """True if ``password`` matches. Never raises for a wrong or malformed hash."""
    try:
        return _hasher(profile).verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str, profile: Profile) -> bool:
    try:
        return _hasher(profile).check_needs_rehash(stored_hash)
    except InvalidHashError:
        return True


@lru_cache
def _dummy_hash(profile: Profile) -> str:
    return hash_password(secrets.token_urlsafe(24), profile)


def burn_verification_time(password: str, profile: Profile) -> None:
    """Spend as long as a real verification, for accounts that can't sign in.

    Without this, "no such account" would answer measurably faster than "wrong
    password", revealing which e-mail addresses have accounts.
    """
    verify_password(_dummy_hash(profile), password, profile)


def password_problems(password: str, *, email: str | None, name: str | None) -> list[str]:
    """Why a new password is not acceptable (empty list if it is).

    The policy follows NIST SP 800-63B: a minimum length, a generous maximum,
    no composition rules, and nothing trivially guessable from the account.
    """
    problems: list[str] = []
    if len(password) < MIN_LENGTH:
        problems.append(f"Use at least {MIN_LENGTH} characters.")
    if len(password) > MAX_LENGTH:
        problems.append(f"Use at most {MAX_LENGTH} characters.")
    if not password.strip():
        problems.append("The password cannot be only spaces.")
    lowered = password.strip().lower()
    for value in (email, name):
        if value and lowered == value.strip().lower():
            problems.append("The password cannot be your e-mail address or name.")
            break
    return problems
