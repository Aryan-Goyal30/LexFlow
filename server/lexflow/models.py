"""SQLAlchemy ORM models (schema history: ``migrations/versions``).

Every table that can hold fictional sample records has an ``is_sample`` flag so
sample data is never mistaken for real saved data.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time
from typing import Any

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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from lexflow.domain import (
    AUDIT_OUTCOMES,
    CASE_PRIORITIES,
    CASE_STATUSES,
    DESCRIPTION_MIN,
    DOCUMENT_NAME_MAX,
    HEARING_SCHEDULED,
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
    """A person who may sign in: staff (Administrator, Advocate, Paralegal) or a Client.

    A user without a ``password_hash`` cannot sign in (for example sample
    advocates until someone sets a password with the CLI). A Client user
    represents one client record (``client_id``); several users may represent
    the same client, such as the contacts of a company.
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(_in_list("role", USER_ROLES), name="role_valid"),
        CheckConstraint("char_length(btrim(name)) > 0", name="name_not_blank"),
        # Client users, and only they, represent a client record.
        CheckConstraint("(role = 'Client') = (client_id IS NOT NULL)", name="client_link"),
        # Signing in needs an e-mail address to sign in with.
        CheckConstraint("password_hash IS NULL OR email IS NOT NULL", name="login_needs_email"),
        CheckConstraint("failed_login_count >= 0", name="failed_login_count_non_negative"),
        Index("uq_users_lower_email", func.lower(text("email")), unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional for people who cannot sign in.
    email: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"), index=True
    )
    # Argon2id hash (PHC string). Never returned by the API or logged.
    password_hash: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    # Set for a temporary password chosen by an administrator.
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    temp_password_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_sample: Mapped[bool] = _is_sample()
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class UserSession(Base):
    """A signed-in browser session.

    Only the SHA-256 of the session token is stored, so a copy of this table
    cannot be used to sign in. Sessions end when revoked (logout, password
    change, deactivation), after ``expires_at``, or after an idle period.
    """

    __tablename__ = "sessions"
    __table_args__ = (CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="token_hash_format"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = _created_at()
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(Text)


class AuditEvent(Base):
    """One security-relevant action: who did what to which record, and the outcome.

    Append-only: a database trigger rejects UPDATE and DELETE (see migration
    0002). Ids are plain values, not foreign keys, so the record outlives the
    rows it describes; the actor's name and role are copied at the time.
    ``details`` holds only whitelisted, non-secret values.
    """

    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(_in_list("outcome", AUDIT_OUTCOMES), name="outcome_valid"),
        CheckConstraint("char_length(action) > 0", name="action_not_blank"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    actor_name: Mapped[str | None] = mapped_column(Text)
    actor_role: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str | None] = mapped_column(Text)
    target_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    case_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


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
    # Archived cases are kept whole but read-only, and hidden from default lists.
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    is_sample: Mapped[bool] = _is_sample()
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    client: Mapped[Client] = relationship(lazy="raise")
    lead_advocate: Mapped[User] = relationship(lazy="raise", foreign_keys=[lead_advocate_id])
    hearings: Mapped[list[Hearing]] = relationship(
        back_populates="case", lazy="raise", cascade="all, delete-orphan", passive_deletes=True
    )
    timeline: Mapped[list[TimelineEvent]] = relationship(
        back_populates="case", lazy="raise", cascade="all, delete-orphan", passive_deletes=True
    )
    documents: Mapped[list[Document]] = relationship(
        back_populates="case", lazy="raise", cascade="all, delete-orphan", passive_deletes=True
    )


class CaseMember(Base):
    """Someone working on a case besides its lead advocate.

    ``member_role`` is ``associate`` (an Advocate) or ``paralegal`` (a
    Paralegal). The lead stays in ``cases.lead_advocate_id``. Who may be added
    is checked by the service (the database cannot compare with users.role).
    """

    __tablename__ = "case_members"
    __table_args__ = (
        CheckConstraint("member_role IN ('associate', 'paralegal')", name="member_role_valid"),
    )

    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True, index=True
    )
    member_role: Mapped[str] = mapped_column(Text, nullable=False)
    added_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    added_at: Mapped[datetime] = _created_at()


class Hearing(Base):
    """A hearing on a case. Cancelled hearings are kept, with the reason; they no
    longer count as the next hearing or appear among upcoming hearings."""

    __tablename__ = "hearings"
    __table_args__ = (
        Index("ix_hearings_case_id_hearing_date", "case_id", "hearing_date"),
        CheckConstraint("status IN ('Scheduled', 'Cancelled')", name="status_valid"),
        CheckConstraint(
            "(status = 'Cancelled') = (cancelled_at IS NOT NULL)",
            name="cancelled_at_matches_status",
        ),
        CheckConstraint(
            "cancellation_reason IS NULL OR char_length(cancellation_reason) BETWEEN 1 AND 500",
            name="cancellation_reason_length",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    hearing_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Unknown until the court lists the matter; never filled with a guess.
    hearing_time: Mapped[time | None] = mapped_column(Time)
    court: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=HEARING_SCHEDULED, server_default=text("'Scheduled'")
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    # NULL for sample hearings and those from before sign-in existed.
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    is_sample: Mapped[bool] = _is_sample()
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

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
    # Who made the change. NULL for sample events, events from before sign-in
    # existed, and events whose user was later removed.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    is_sample: Mapped[bool] = _is_sample()
    # Stamped by the application, not the database: PostgreSQL's now() is the
    # start of the transaction, so two events written in one transaction would
    # tie and come back in arbitrary order. (The server default stays for rows
    # inserted by SQL.)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    case: Mapped[Case] = relationship(back_populates="timeline", lazy="raise")


class Document(Base):
    """A document on a case.

    Uploaded documents have a stored file (``storage_key``, ``sha256``,
    ``size_bytes``, ``content_type``). Sample records have none of these and
    keep only the size label from the sample data.

    Deleting a document sets ``deleted_at`` and keeps the row and its file, so
    it can be restored; only ``python -m lexflow.cli.documents purge`` removes
    them for good. Names are unique per case among live documents only.

    A document reaches the client portal only once an advocate on the case
    shares it (``shared_with_client_at``); deleting it stops the sharing.
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
        CheckConstraint(
            "deleted_by_id IS NULL OR deleted_at IS NOT NULL", name="deleted_by_needs_deleted_at"
        ),
        CheckConstraint(
            "shared_by_id IS NULL OR shared_with_client_at IS NOT NULL",
            name="shared_by_needs_shared_at",
        ),
        CheckConstraint(
            "deleted_at IS NULL OR shared_with_client_at IS NULL", name="deleted_never_shared"
        ),
        CheckConstraint(
            "shared_with_client_at IS NULL OR storage_key IS NOT NULL", name="shared_needs_file"
        ),
        Index(
            "uq_documents_case_id_lower_name",
            "case_id",
            func.lower(text("name")),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
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
    # NULL for sample records and for uploads from before sign-in existed.
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # Shared with the case's client (client portal): explicit, by an advocate.
    shared_with_client_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    shared_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    is_sample: Mapped[bool] = _is_sample()
    created_at: Mapped[datetime] = _created_at()

    case: Mapped[Case] = relationship(back_populates="documents", lazy="raise")

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

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
