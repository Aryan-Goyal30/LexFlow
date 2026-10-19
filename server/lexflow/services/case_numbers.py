"""Case-number allocation: ``LF-<year>-<sequence>``, unique and gap-tolerant.

One atomic statement per allocation::

    INSERT INTO case_number_counters (year, last_value) VALUES (:year, <start>)
    ON CONFLICT (year) DO UPDATE SET last_value = case_number_counters.last_value + 1
    RETURNING last_value

The upsert locks the year's counter row until the transaction ends, so
concurrent requests are serialised by PostgreSQL and can never receive the same
number. A rolled-back transaction leaves a gap, which is acceptable.

The first allocation of a year starts above any case number already stored for
that year (for example cases imported without a counter).
"""

from __future__ import annotations

from sqlalchemy import Integer, cast, func, literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from lexflow.models import Case, CaseNumberCounter


def format_case_number(year: int, sequence: int) -> str:
    return f"LF-{year}-{sequence:04d}"


def allocate_case_number(session: Session, year: int) -> str:
    prefix = f"LF-{year}-"
    highest_existing = (
        select(
            func.coalesce(
                func.max(cast(func.substr(Case.case_number, len(prefix) + 1), Integer)), 0
            )
        )
        .where(Case.case_number.like(prefix + "%"))
        .scalar_subquery()
    )
    statement = (
        insert(CaseNumberCounter)
        .values(year=year, last_value=highest_existing + literal(1))
        .on_conflict_do_update(
            index_elements=[CaseNumberCounter.year],
            set_={"last_value": CaseNumberCounter.last_value + 1},
        )
        .returning(CaseNumberCounter.last_value)
    )
    sequence = session.execute(statement).scalar_one()
    return format_case_number(year, sequence)
