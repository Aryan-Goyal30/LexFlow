"""Load the fictional sample data into the database.

Repeat-safe: every row has a deterministic UUID and is inserted with
``ON CONFLICT (id) DO NOTHING``, so a second run adds nothing. Every row is
marked ``is_sample = true``. Sample documents have no stored file.

Contact details of existing *sample* people are brought up to date on every run
(an older database may still hold earlier addresses); rows that are not sample
data are never changed. Loading sample data never sets a password: sample
people cannot sign in until someone sets one with ``python -m lexflow.cli.users``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, time
from importlib import resources
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from lexflow.models import (
    Base,
    Case,
    CaseNumberCounter,
    Client,
    Document,
    Hearing,
    TimelineEvent,
    User,
)
from lexflow.seed import sample_uuid

CASE_NUMBER = re.compile(r"^LF-(\d{4})-(\d{4,})$")


def read_sample_data() -> dict[str, Any]:
    text = resources.files("lexflow.seed").joinpath("sample_data.json").read_text("utf-8")
    data: dict[str, Any] = json.loads(text)
    return data


@dataclass
class LoadResult:
    inserted: dict[str, int] = field(default_factory=dict)
    # Existing sample rows whose contact details were brought up to date.
    updated: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.inserted.values())


def _insert(session: Session, model: type[Base], rows: list[dict[str, Any]]) -> int:
    """Insert rows that don't exist yet; return how many were actually inserted."""
    if not rows:
        return 0
    statement = (
        insert(model)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["id"])
        # rowcount is -1 for batched inserts with psycopg, so count returned ids.
        .returning(model.__table__.c.id)
    )
    return len(session.execute(statement).all())


def load_sample_data(session: Session, data: dict[str, Any] | None = None) -> LoadResult:
    """Insert any missing sample rows and sync the case-number counters.

    The caller commits. Raises ``sqlalchemy.exc.IntegrityError`` if a sample
    case number is already used by a real case.
    """
    data = data or read_sample_data()
    result = LoadResult()

    advocate_id = {a["name"]: sample_uuid("advocate", a["name"]) for a in data["advocates"]}
    client_id = {c["legacyId"]: sample_uuid("client", c["legacyId"]) for c in data["clients"]}

    result.inserted["users"] = _insert(
        session,
        User,
        [
            {
                "id": advocate_id[a["name"]],
                "name": a["name"],
                "email": a["email"],
                "role": "Advocate",
                "is_sample": True,
            }
            for a in data["advocates"]
        ],
    )
    result.inserted["clients"] = _insert(
        session,
        Client,
        [
            {
                "id": client_id[c["legacyId"]],
                "name": c["name"],
                "email": c["email"],
                "phone": c["phone"],
                "company": c["company"],
                "is_sample": True,
            }
            for c in data["clients"]
        ],
    )

    cases, hearings, events, documents = [], [], [], []
    for c in data["cases"]:
        case_id = sample_uuid("case", c["legacyId"])
        cases.append(
            {
                "id": case_id,
                "case_number": c["caseNumber"],
                "title": c["title"],
                "status": c["status"],
                "priority": c["priority"],
                "practice_area": c["practiceArea"],
                "client_id": client_id[c["clientLegacyId"]],
                "lead_advocate_id": advocate_id[c["leadAdvocate"]],
                "court_name": c["courtName"],
                "opposing_party": c["opposingParty"],
                "description": c["description"],
                "opened_on": date.fromisoformat(c["openedOn"]),
                "is_sample": True,
            }
        )
        hearings += [
            {
                "id": sample_uuid("hearing", h["legacyId"]),
                "case_id": case_id,
                "hearing_date": date.fromisoformat(h["date"]),
                "hearing_time": time.fromisoformat(h["time"]) if h["time"] else None,
                "court": h["court"],
                "purpose": h["purpose"],
                "is_sample": True,
            }
            for h in c["hearings"]
        ]
        events += [
            {
                "id": sample_uuid("event", t["legacyId"]),
                "case_id": case_id,
                "event_date": date.fromisoformat(t["date"]),
                "label": t["label"],
                "description": t["description"],
                "actor_id": None,
                "is_sample": True,
            }
            for t in c["timeline"]
        ]
        documents += [
            {
                "id": sample_uuid("document", d["legacyId"]),
                "case_id": case_id,
                "name": d["name"],
                "document_type": d["type"],
                "size_label": d["sizeLabel"],
                "uploaded_on": date.fromisoformat(d["uploadedOn"]),
                "is_sample": True,
            }
            for d in c["documents"]
        ]

    result.inserted["cases"] = _insert(session, Case, cases)
    result.inserted["hearings"] = _insert(session, Hearing, hearings)
    result.inserted["timeline_events"] = _insert(session, TimelineEvent, events)
    result.inserted["documents"] = _insert(session, Document, documents)

    result.updated["users"] = _sync_contacts(
        session, User, {advocate_id[a["name"]]: {"email": a["email"]} for a in data["advocates"]}
    )
    result.updated["clients"] = _sync_contacts(
        session,
        Client,
        {
            client_id[c["legacyId"]]: {"email": c["email"], "phone": c["phone"]}
            for c in data["clients"]
        },
    )

    _sync_counters(session, [c["caseNumber"] for c in data["cases"]])
    return result


def _sync_contacts(
    session: Session, model: type[User] | type[Client], values: dict[Any, dict[str, str]]
) -> int:
    """Update contact fields of sample rows that differ. Never touches other rows."""
    changed = 0
    for row_id, fields in values.items():
        differs = [getattr(model, name).is_distinct_from(value) for name, value in fields.items()]
        statement = (
            update(model)
            .where(model.id == row_id, model.is_sample.is_(True), or_(*differs))
            .values(**fields)
            .returning(model.id)
        )
        changed += len(session.execute(statement).all())
    return changed


def _sync_counters(session: Session, case_numbers: list[str]) -> None:
    """Make sure new case numbers start above every sample case number."""
    highest: dict[int, int] = {}
    for number in case_numbers:
        match = CASE_NUMBER.match(number)
        if match:
            year, seq = int(match[1]), int(match[2])
            highest[year] = max(highest.get(year, 0), seq)
    for year, seq in highest.items():
        statement = insert(CaseNumberCounter).values(year=year, last_value=seq)
        statement = statement.on_conflict_do_update(
            index_elements=["year"],
            set_={"last_value": func.greatest(CaseNumberCounter.last_value, seq)},
        )
        session.execute(statement)


def sample_row_counts(session: Session) -> dict[str, int]:
    """How many sample rows each table holds."""
    counts: dict[str, int] = {}
    for model in (User, Client, Case, Hearing, TimelineEvent, Document):
        is_sample = model.is_sample
        counts[model.__tablename__] = (
            session.scalar(select(func.count()).select_from(model).where(is_sample.is_(True))) or 0
        )
    return counts
