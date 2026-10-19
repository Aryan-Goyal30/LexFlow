"""SQLAlchemy ORM models for the Phase 1 schema.

Every table that can hold fictional sample records has an ``is_sample`` flag so
sample data is never mistaken for real saved data.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    Time,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from lexflow.domain import (
    CASE_PRIORITIES,
    CASE_STATUSES,
    DESCRIPTION_MIN,
    DOCUMENT_NAME_MAX,
    PRACTICE_AREAS,
    TITLE_MAX,
    TITLE_MIN,
    USER_ROLES,
)

# Stable constraint names, so migrations can refer to them.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def _in_list(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join("'" + v.replace("'", "''") + "'" for v in values)
    return f"{column} IN ({quoted})"


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


def _is_sample() -> Mapped[bool]:
    return mapped_column(Boolean, nullable=False, server_default=text("false"))


class User(Base):
    """A person in the firm. Phase 1 uses it for advocates; there are no credentials."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(_in_list("role", USER_ROLES), name="role_valid"),
        CheckConstraint("char_length(btrim(name)) > 0", name="name_not_blank"),
        Index("uq_users_lower_email", func.lower(text("email")), unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional: the sample data has no e-mail address for most advocates.
    email: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    is_sample: Mapped[bool] = _is_sample()
    created_at: Mapped[datetime] = _created_at()


class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (CheckConstraint("char_length(btrim(name)) > 0", name="name_not_blank"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    company: Mapped[str | None] = mapped_column(Text)
    is_sample: Mapped[bool] = _is_sample()
    created_at: Mapped[datetime] = _created_at()


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (
        CheckConstraint(_in_list("status", CASE_STATUSES), name="status_valid"),
        CheckConstraint(_in_list("priority", CASE_PRIORITIES), name="priority_valid"),
        CheckConstraint(_in_list("practice_area", PRACTICE_AREAS), name="practice_area_valid"),
        CheckConstraint(
            f"char_length(btrim(title)) BETWEEN {TITLE_MIN} AND {TITLE_MAX}", name="title_length"
        ),
        CheckConstraint(
            f"char_length(btrim(description)) >= {DESCRIPTION_MIN}", name="description_length"
        ),
        CheckConstraint(r"case_number ~ '^LF-[0-9]{4}-[0-9]{4,}$'", name="case_number_format"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(Text, nullable=False)
    practice_area: Mapped[str] = mapped_column(Text, nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    lead_advocate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    court_name: Mapped[str | None] = mapped_column(Text)
    opposing_party: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    opened_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_sample: Mapped[bool] = _is_sample()
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    client: Mapped[Client] = relationship(lazy="raise")
    lead_advocate: Mapped[User] = relationship(lazy="raise")
    hearings: Mapped[list[Hearing]] = relationship(
        back_populates="case", lazy="raise", cascade="all, delete-orphan", passive_deletes=True
    )
    timeline: Mapped[list[TimelineEvent]] = relationship(
        back_populates="case", lazy="raise", cascade="all, delete-orphan", passive_deletes=True
    )
    documents: Mapped[list[Document]] = relationship(
        back_populates="case", lazy="raise", cascade="all, delete-orphan", passive_deletes=True
    )


class Hearing(Base):
    __tablename__ = "hearings"
    __table_args__ = (Index("ix_hearings_case_id_hearing_date", "case_id", "hearing_date"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    hearing_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Unknown until the court lists the matter; never filled with a guess.
    hearing_time: Mapped[time | None] = mapped_column(Time)
    court: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    is_sample: Mapped[bool] = _is_sample()
    created_at: Mapped[datetime] = _created_at()

    case: Mapped[Case] = relationship(back_populates="hearings", lazy="raise")


class TimelineEvent(Base):
    __tablename__ = "timeline_events"
    __table_args__ = (Index("ix_timeline_events_case_id_event_date", "case_id", "event_date"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # NULL means the event was recorded by the system without a signed-in user.
    # Phase 1 has no authentication, so every new event has no actor.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    is_sample: Mapped[bool] = _is_sample()
    created_at: Mapped[datetime] = _created_at()

    case: Mapped[Case] = relationship(back_populates="timeline", lazy="raise")


class Document(Base):
    """A document on a case.

    Uploaded documents have a stored file (``storage_key``, ``sha256``,
    ``size_bytes``, ``content_type``). Sample records have none of these and
    keep only the size label from the sample data.
    """

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(f"char_length(name) BETWEEN 1 AND {DOCUMENT_NAME_MAX}", name="name_length"),
        CheckConstraint("size_bytes IS NULL OR size_bytes > 0", name="size_bytes_positive"),
        CheckConstraint("sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        CheckConstraint(
            "storage_key IS NULL OR storage_key ~ '^[0-9a-f]{32}$'", name="storage_key_format"
        ),
        CheckConstraint(
            "(storage_key IS NULL AND sha256 IS NULL AND content_type IS NULL)"
            " OR (storage_key IS NOT NULL AND sha256 IS NOT NULL"
            " AND content_type IS NOT NULL AND size_bytes IS NOT NULL)",
            name="stored_file_complete",
        ),
        CheckConstraint("size_bytes IS NOT NULL OR size_label IS NOT NULL", name="has_size"),
        Index("uq_documents_case_id_lower_name", "case_id", func.lower(text("name")), unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(DOCUMENT_NAME_MAX), nullable=False)
    document_type: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    size_label: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(Text)
    storage_key: Mapped[str | None] = mapped_column(Text, unique=True)
    uploaded_on: Mapped[date] = mapped_column(Date, nullable=False)
    is_sample: Mapped[bool] = _is_sample()
    created_at: Mapped[datetime] = _created_at()

    case: Mapped[Case] = relationship(back_populates="documents", lazy="raise")

    @property
    def has_file(self) -> bool:
        return self.storage_key is not None


class CaseNumberCounter(Base):
    """Last case-number sequence used per year (Asia/Kolkata calendar year)."""

    __tablename__ = "case_number_counters"
    __table_args__ = (
        CheckConstraint("year BETWEEN 2000 AND 9999", name="year_range"),
        CheckConstraint("last_value >= 0", name="last_value_non_negative"),
    )

    year: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False)
