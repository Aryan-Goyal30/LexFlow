"""Load the fictional sample data: ``python -m lexflow.seed``.

Development only. Refuses to run unless ``LEXFLOW_ENV=development``, so sample
records can never be loaded into a production-like database by accident.
"""

from __future__ import annotations

import sys

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from lexflow.config import get_settings
from lexflow.db import engine_for
from lexflow.seed.loader import load_sample_data


def main() -> int:
    settings = get_settings()
    if settings.env != "development":
        print(
            f"Refusing to load sample data: LEXFLOW_ENV is {settings.env!r}. "
            "Sample data can only be loaded when LEXFLOW_ENV=development.",
            file=sys.stderr,
        )
        return 2

    try:
        with Session(engine_for(settings.database_url)) as session, session.begin():
            result = load_sample_data(session)
    except OperationalError:
        print("Could not connect to the database. Is it running?", file=sys.stderr)
        return 1
    except IntegrityError:
        print(
            "Sample data conflicts with existing records (for example a case number "
            "already in use). Nothing was loaded.",
            file=sys.stderr,
        )
        return 1

    refreshed = sum(result.updated.values())
    if refreshed:
        print(f"Updated the fictional contact details of {refreshed} existing sample records.")
    if result.total == 0:
        print("Sample data already loaded; nothing to add.")
    else:
        added = ", ".join(f"{n} {table}" for table, n in result.inserted.items() if n)
        print(f"Loaded fictional sample data: {added}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
