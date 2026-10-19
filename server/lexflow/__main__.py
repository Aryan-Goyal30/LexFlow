"""Start the API: ``python -m lexflow``.

Start-up refusals (exit status 2), checked before the server starts:

- Listening on anything but a loopback address. LexFlow has sign-in and
  role-based access now, but it has not been reviewed for exposure to a
  network; it stays on this computer until that is a deliberate decision.
- ``LEXFLOW_ENV=production`` without ``LEXFLOW_COOKIE_SECURE=true``: the
  session cookie must never travel over plain HTTP outside development.
- ``LEXFLOW_ENV=production`` while a fictional sample account can sign in.

These live here rather than in ``create_app`` so the application (and its
OpenAPI document) is the same in every environment.
"""

from __future__ import annotations

import logging
import sys

import uvicorn
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from lexflow.config import LOOPBACK_HOSTS, Settings, get_settings
from lexflow.db import engine_for
from lexflow.models import User


def refusal(settings: Settings) -> str | None:
    if settings.api_host not in LOOPBACK_HOSTS:
        return (
            f"Refusing to listen on {settings.api_host!r}: LexFlow is for use on this "
            "computer only and must stay on 127.0.0.1."
        )
    if settings.env == "production" and not settings.cookie_secure:
        return (
            "Refusing to start: LEXFLOW_ENV=production requires LEXFLOW_COOKIE_SECURE=true "
            "(and HTTPS in front of the API)."
        )
    if settings.env == "production":
        try:
            with Session(engine_for(settings.database_url)) as session:
                sample_logins = session.scalar(
                    select(func.count())
                    .select_from(User)
                    .where(User.is_sample.is_(True), User.password_hash.is_not(None))
                )
        except DBAPIError:
            return "Refusing to start: the database could not be checked."
        if sample_logins:
            return (
                "Refusing to start: fictional sample accounts can sign in. Remove their "
                "passwords or use a database without sample data."
            )
    return None


def main() -> int:
    settings = get_settings()
    reason = refusal(settings)
    if reason is not None:
        print(reason, file=sys.stderr)
        return 2
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    uvicorn.run(
        "lexflow.main:create_app",
        factory=True,
        host=settings.api_host,
        port=settings.api_port,
        access_log=False,  # lexflow.access logs requests instead
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
