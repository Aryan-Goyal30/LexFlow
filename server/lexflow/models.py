"""SQLAlchemy ORM models (schema history: ``migrations/versions``).

Every table that can hold fictional sample records has an ``is_sample`` flag so
sample data is never mistaken for real saved data.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from lexflow.domain import (
    ANALYSIS_REASON_MAX,
    ANALYSIS_STATUSES,
    AUDIT_OUTCOMES,
    CASE_PRIORITIES,
    CASE_STATUSES,
    DESCRIPTION_MIN,
    DOCUMENT_NAME_MAX,
    EXTRACTION_REASON_MAX,
    EXTRACTION_STATUSES,
    FINDING_KINDS,
    FINDING_PREFIX,
    HEARING_SCHEDULED,
    INDEX_STATUSES,
    PRACTICE_AREAS,
    REVIEW_NOTE_MAX,
    REVIEW_STATUSES,
    REVIEW_TEXT_MAX,
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


class DocumentExtraction(Base):
    """The text-extraction job of one stored document, and its outcome.

    Created when a file is uploaded (or re-queued). The worker
    (``python -m lexflow.worker``) claims ``queued`` jobs; a claim is a lease,
    so a job whose worker died is taken over once the lease has expired.
    ``failed`` and ``unsupported`` always carry a reason. ``index_status`` says
    whether the chunks have embeddings (``disabled`` unless configured).
    """

    __tablename__ = "document_extractions"
    __table_args__ = (
        CheckConstraint(_in_list("status", EXTRACTION_STATUSES), name="status_valid"),
        CheckConstraint(_in_list("index_status", INDEX_STATUSES), name="index_status_valid"),
        CheckConstraint(
            "(status IN ('failed', 'unsupported')) = (reason_code IS NOT NULL)",
            name="reason_matches_status",
        ),
        CheckConstraint(
            f"reason IS NULL OR char_length(reason) <= {EXTRACTION_REASON_MAX}",
            name="reason_length",
        ),
        CheckConstraint(
            "(status = 'processing') = (lease_expires_at IS NOT NULL)",
            name="lease_matches_status",
        ),
        CheckConstraint("attempts >= 0", name="attempts_non_negative"),
        Index("ix_document_extractions_status_queued_at", "status", "queued_at"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    # A stable code (for example "no-text-layer") and a message for people.
    reason_code: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(Text)
    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # What produced the text, e.g. "pypdf 6.1.3", and its size.
    extractor: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)  # PDFs only
    section_count: Mapped[int | None] = mapped_column(Integer)
    char_count: Mapped[int | None] = mapped_column(Integer)
    chunk_count: Mapped[int | None] = mapped_column(Integer)
    index_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'disabled'")
    )
    index_reason: Mapped[str | None] = mapped_column(Text)
    embedding_model: Mapped[str | None] = mapped_column(Text)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DocumentSection(Base):
    """Extracted text of one PDF page, or one numbered part of a document
    without pages (Word, text). ``page_number`` is null when there are no pages:
    page numbers are never invented."""

    __tablename__ = "document_sections"
    __table_args__ = (
        CheckConstraint("number >= 1", name="number_positive"),
        CheckConstraint("page_number IS NULL OR page_number >= 1", name="page_number_positive"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    number: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_number: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, nullable=False)


class DocumentChunk(Base):
    """A passage of a section's text. ``char_start``/``char_end`` locate it in
    the section's text exactly (``text`` is that slice); chunks never cross a
    section, so each has one page (or none)."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "section_number"],
            ["document_sections.document_id", "document_sections.number"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("document_id", "number"),
        CheckConstraint("number >= 1", name="number_positive"),
        CheckConstraint("char_start >= 0 AND char_end > char_start", name="offsets_valid"),
        CheckConstraint("char_length(text) = char_end - char_start", name="text_matches_offsets"),
        CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="content_sha256_format"),
        CheckConstraint("page_number IS NULL OR page_number >= 1", name="page_number_positive"),
        Index("ix_document_chunks_document_id_section_number", "document_id", "section_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    section_number: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class DocumentChunkEmbedding(Base):
    """The vector of one chunk under one model (pgvector; migration 0009).

    ``content_sha256`` is the chunk's hash when it was embedded, so a vector
    never outlives the text it was computed from; ``model`` names the model and
    revision, so vectors of different models are never compared. Deleting a
    chunk (re-extraction, purge) deletes its vectors.
    """

    __tablename__ = "document_chunk_embeddings"
    __table_args__ = (
        CheckConstraint("dimensions = vector_dims(embedding)", name="dimensions_match"),
        CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="content_sha256_format"),
        CheckConstraint("char_length(model) BETWEEN 1 AND 200", name="model_length"),
        Index("ix_document_chunk_embeddings_document_id_model", "document_id", "model"),
    )

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"), primary_key=True
    )
    model: Mapped[str] = mapped_column(Text, primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    content_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class JudgmentSource(Base):
    """Where judgments come from, and the terms of use recorded for it (Phase 4).

    Every judgment names its source. ``terms_*`` and ``permitted_use`` record
    who read the source's terms, when, where, and what they permit; LexFlow
    does not decide that. ``is_synthetic`` marks invented test data, which the
    importer accepts only into test databases and the app labels everywhere.
    """

    __tablename__ = "judgment_sources"
    __table_args__ = (
        CheckConstraint("key ~ '^[a-z0-9][a-z0-9-]{1,62}$'", name="key_format"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 200", name="name_length"),
        CheckConstraint("terms_url ~ '^https://'", name="terms_url_https"),
        CheckConstraint(
            "char_length(terms_checked_by) BETWEEN 1 AND 200", name="checked_by_length"
        ),
        CheckConstraint(
            "char_length(permitted_use) BETWEEN 1 AND 2000", name="permitted_use_length"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    terms_url: Mapped[str] = mapped_column(Text, nullable=False)
    terms_checked_on: Mapped[date] = mapped_column(Date, nullable=False)
    terms_checked_by: Mapped[str] = mapped_column(Text, nullable=False)
    permitted_use: Mapped[str] = mapped_column(Text, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Judgment(Base):
    """A judgment in the collection: metadata as supplied, text as extracted.

    The id is derived from the source and the source's own identifier, so
    importing the same judgment again finds the same row. Optional metadata
    (citation, date, bench) is stored only when the import supplied it.
    """

    __tablename__ = "judgments"
    __table_args__ = (
        UniqueConstraint("source_id", "source_document_id"),
        CheckConstraint(
            "char_length(source_document_id) BETWEEN 1 AND 200", name="source_document_id_length"
        ),
        CheckConstraint("source_url ~ '^https://'", name="source_url_https"),
        CheckConstraint("char_length(title) BETWEEN 1 AND 500", name="title_length"),
        CheckConstraint("char_length(court) BETWEEN 1 AND 200", name="court_length"),
        CheckConstraint(
            "citation IS NULL OR char_length(citation) BETWEEN 1 AND 200", name="citation_length"
        ),
        CheckConstraint("year IS NULL OR year BETWEEN 1800 AND 2100", name="year_range"),
        CheckConstraint(
            "decision_date IS NULL OR year = EXTRACT(YEAR FROM decision_date)",
            name="year_matches_date",
        ),
        CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="content_sha256_format"),
        CheckConstraint(_in_list("index_status", INDEX_STATUSES), name="index_status_valid"),
        Index("ix_judgments_court_year", "court", "year"),
        Index(
            "uq_judgments_citation",
            func.lower(text("citation")),
            unique=True,
            postgresql_where=text("citation IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("judgment_sources.id", ondelete="RESTRICT"), nullable=False
    )
    source_document_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    court: Mapped[str] = mapped_column(Text, nullable=False)
    citation: Mapped[str | None] = mapped_column(Text)
    decision_date: Mapped[date | None] = mapped_column(Date)
    year: Mapped[int | None] = mapped_column(Integer)
    bench: Mapped[str | None] = mapped_column(Text)
    practice_areas: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    extractor: Mapped[str] = mapped_column(Text, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    section_count: Mapped[int] = mapped_column(Integer, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    imported_by: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    index_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'disabled'")
    )
    embedding_model: Mapped[str | None] = mapped_column(Text)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JudgmentSection(Base):
    """The extracted text of one page (PDF) or part of a judgment."""

    __tablename__ = "judgment_sections"
    __table_args__ = (
        CheckConstraint("number >= 1", name="number_positive"),
        CheckConstraint("page_number IS NULL OR page_number >= 1", name="page_number_positive"),
    )

    judgment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("judgments.id", ondelete="CASCADE"), primary_key=True
    )
    number: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, nullable=False)


class JudgmentChunk(Base):
    """A passage of a judgment section, with a full-text vector kept by the database."""

    __tablename__ = "judgment_chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["judgment_id", "section_number"],
            ["judgment_sections.judgment_id", "judgment_sections.number"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("judgment_id", "number"),
        CheckConstraint("number >= 1", name="number_positive"),
        CheckConstraint("char_start >= 0 AND char_end > char_start", name="offsets_valid"),
        CheckConstraint("char_length(text) = char_end - char_start", name="text_matches_offsets"),
        CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="content_sha256_format"),
        Index("ix_judgment_chunks_search_vector", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    judgment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("judgments.id", ondelete="CASCADE"), nullable=False
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    section_number: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    search_vector: Mapped[Any] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english'::regconfig, text)", persisted=True)
    )


class JudgmentChunkEmbedding(Base):
    """The vector of one judgment chunk under one model (like DocumentChunkEmbedding)."""

    __tablename__ = "judgment_chunk_embeddings"
    __table_args__ = (
        CheckConstraint("dimensions = vector_dims(embedding)", name="dimensions_match"),
        CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="content_sha256_format"),
        CheckConstraint("char_length(model) BETWEEN 1 AND 200", name="model_length"),
        Index("ix_judgment_chunk_embeddings_judgment_id_model", "judgment_id", "model"),
    )

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("judgment_chunks.id", ondelete="CASCADE"), primary_key=True
    )
    model: Mapped[str] = mapped_column(Text, primary_key=True)
    judgment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("judgments.id", ondelete="CASCADE"), nullable=False
    )
    content_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class AnalysisRun(Base):
    """One AI case analysis (Phase 5): what was asked, what was sent, what survived.

    Created ``queued`` by the API; the worker claims it with a lease (like
    document extraction), assembles the evidence, calls the configured
    provider and stores only the **validated** result: every fact, quote and
    precedent in ``result`` points at evidence listed in ``evidence``. Raw
    model output is never stored. ``evidence`` holds references and content
    hashes, not the text itself. ``removed`` counts what validation dropped.
    At most one run per case is waiting or running at a time.
    """

    __tablename__ = "analysis_runs"
    __table_args__ = (
        CheckConstraint(_in_list("status", ANALYSIS_STATUSES), name="status_valid"),
        CheckConstraint(
            "(status = 'failed') = (reason_code IS NOT NULL)", name="reason_matches_status"
        ),
        CheckConstraint(
            f"reason IS NULL OR char_length(reason) <= {ANALYSIS_REASON_MAX}",
            name="reason_length",
        ),
        CheckConstraint(
            "(status = 'running') = (lease_expires_at IS NOT NULL)", name="lease_matches_status"
        ),
        CheckConstraint("(status = 'ready') = (result IS NOT NULL)", name="result_matches_status"),
        CheckConstraint("attempts >= 0", name="attempts_non_negative"),
        CheckConstraint("char_length(provider) BETWEEN 1 AND 50", name="provider_length"),
        CheckConstraint("char_length(model) BETWEEN 1 AND 100", name="model_length"),
        CheckConstraint(
            "char_length(prompt_version) BETWEEN 1 AND 50", name="prompt_version_length"
        ),
        Index("ix_analysis_runs_case_id_created_at", "case_id", "created_at"),
        Index("ix_analysis_runs_status_available_at", "status", "available_at"),
        Index("ix_analysis_runs_requested_by_id_created_at", "requested_by_id", "created_at"),
        Index(
            "uq_analysis_runs_case_id_active",
            "case_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    # A stable code (for example "provider-timeout") and a message for people.
    reason_code: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # A waiting run is not claimed before this (a pause after a busy provider).
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(Text)
    # Which provider and model were asked, and the prompt's version.
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    # The request: selected document ids and the limits in force.
    selection: Mapped[dict[str, Any]] = mapped_column(JSONB(none_as_null=True), nullable=False)
    # The evidence sent (ids -> references and content hashes), once assembled.
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    removed: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    # Token counts reported by the provider, if any. (``none_as_null``: Python
    # None is stored as SQL NULL, not as JSON null, so the checks above hold.)
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


_KIND_MATCHES_ID = (
    "left(finding_id, 1) = CASE finding_kind "
    + " ".join(f"WHEN '{kind}' THEN '{prefix}'" for kind, prefix in FINDING_PREFIX.items())
    + " END"
)


def _review_checks() -> tuple[CheckConstraint, ...]:
    """The rules shared by a finding's current review and each history entry."""
    return (
        CheckConstraint(_in_list("status", REVIEW_STATUSES), name="status_valid"),
        CheckConstraint(_in_list("finding_kind", FINDING_KINDS), name="finding_kind_valid"),
        CheckConstraint("finding_id ~ '^[FIPC][1-9][0-9]{0,3}$'", name="finding_id_format"),
        CheckConstraint(_KIND_MATCHES_ID, name="finding_kind_matches_id"),
        CheckConstraint(
            "(status = 'edited') = (reviewed_text IS NOT NULL)", name="text_matches_status"
        ),
        CheckConstraint(
            f"reviewed_text IS NULL OR char_length(reviewed_text) BETWEEN 1 AND {REVIEW_TEXT_MAX}",
            name="reviewed_text_length",
        ),
        CheckConstraint(
            f"note IS NULL OR char_length(note) BETWEEN 1 AND {REVIEW_NOTE_MAX}",
            name="note_length",
        ),
        CheckConstraint("version >= 1", name="version_positive"),
    )


class AnalysisFindingReview(Base):
    """A lawyer's current decision on one finding of one analysis run (Phase 6).

    A finding is identified by its run and its id in that run's result (F2,
    I1, P1, C1: ids are unique only within a run). The run's ``result`` is
    never changed: an edit is stored here as ``reviewed_text`` and the
    model's wording stays in the run. No row means the finding is unreviewed;
    clearing a decision sets ``unreviewed`` and keeps the history. Every
    change increments ``version`` and adds an ``AnalysisFindingReviewEvent``
    in the same transaction.
    """

    __tablename__ = "analysis_finding_reviews"
    __table_args__ = (
        *_review_checks(),
        UniqueConstraint("run_id", "finding_id"),
        Index("ix_analysis_finding_reviews_case_id", "case_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    finding_kind: Mapped[str] = mapped_column(Text, nullable=False)
    finding_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    # The lawyer's wording, only for status "edited".
    reviewed_text: Mapped[str | None] = mapped_column(Text)
    # Private to reviewers: never on the timeline, in audit details or in briefs.
    note: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )


class AnalysisFindingReviewEvent(Base):
    """One change to a finding's review, kept forever (append-only history).

    Holds the state after the change (status, wording, note) with who made it
    and when. ``version`` matches the review's version after the change, so
    (review, version) is unique and a retried request cannot add a second
    entry for the same change. These rows also appear on the matter timeline
    (without the wording or note), derived at read time: they are never
    written to ``timeline_events``, which the analysis evidence reads.
    """

    __tablename__ = "analysis_finding_review_events"
    __table_args__ = (
        *_review_checks(),
        UniqueConstraint("review_id", "version"),
        Index("ix_analysis_finding_review_events_case_id_occurred_at", "case_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    review_id: Mapped[uuid.UUID] = mapped_column(
        # Named explicitly: the generated name would exceed PostgreSQL's 63 characters.
        ForeignKey(
            "analysis_finding_reviews.id",
            ondelete="CASCADE",
            name="fk_analysis_finding_review_events_review_id",
        ),
        nullable=False,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    finding_kind: Mapped[str] = mapped_column(Text, nullable=False)
    finding_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_text: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )


class CaseNumberCounter(Base):
    """Last case-number sequence used per year (Asia/Kolkata calendar year)."""

    __tablename__ = "case_number_counters"
    __table_args__ = (
        CheckConstraint("year BETWEEN 2000 AND 9999", name="year_range"),
        CheckConstraint("last_value >= 0", name="last_value_non_negative"),
    )

    year: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False)
