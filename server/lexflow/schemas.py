"""Request and response models.

JSON uses camelCase to match the TypeScript front end (``src/types``). Python
code uses snake_case; the alias generator translates. Validation messages match
the ones the front end shows, so server errors can sit beside the right field.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from lexflow.domain import (
    CANCELLATION_REASON_MAX,
    DESCRIPTION_MAX,
    DESCRIPTION_MIN,
    HEARING_TEXT_MAX,
    SHORT_TEXT_MAX,
    TITLE_MAX,
    TITLE_MIN,
    AuditOutcome,
    CasePriority,
    CaseStatus,
    ExtractionStatus,
    HearingStatus,
    IndexStatus,
    PracticeArea,
    UserRole,
)

TITLE_MESSAGE = f"Enter a descriptive case title (at least {TITLE_MIN} characters)."
TITLE_TOO_LONG = f"Keep the case title under {TITLE_MAX + 1} characters."
DESCRIPTION_MESSAGE = f"Provide a short summary (at least {DESCRIPTION_MIN} characters)."
DESCRIPTION_TOO_LONG = f"Keep the summary under {DESCRIPTION_MAX + 1} characters."
SHORT_TEXT_TOO_LONG = f"Keep this under {SHORT_TEXT_MAX + 1} characters."
NOT_EMPTY = "This field cannot be empty."
INVALID_CHARACTER = "Remove the invalid character (a null byte) from this field."


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class InputModel(ApiModel):
    """Request bodies: unknown fields are an error, not silently ignored."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    @field_validator("*", mode="before")
    @classmethod
    def _no_nul(cls, value: Any) -> Any:
        # PostgreSQL text cannot store NUL; reject it here as a field error.
        if isinstance(value, str) and "\x00" in value:
            raise ValueError(INVALID_CHARACTER)
        return value


# --- reference data -----------------------------------------------------------


class SecretInputModel(ApiModel):
    """Bodies that carry passwords: unknown fields are an error, and text is NOT
    stripped (spaces at either end are part of a password)."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def _no_nul(cls, value: Any) -> Any:
        if isinstance(value, str) and "\x00" in value:
            raise ValueError(INVALID_CHARACTER)
        return value


# --- sign-in ----------------------------------------------------------------------


class SignInIn(SecretInputModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=1024)


class PasswordChangeIn(SecretInputModel):
    current_password: str = Field(max_length=1024)
    new_password: str = Field(max_length=1024)


class MeOut(ApiModel):
    """The signed-in user. Never includes password or session details."""

    id: uuid.UUID
    name: str
    email: str | None
    role: UserRole
    client_id: uuid.UUID | None = Field(
        description="For Client users: the client record they represent."
    )
    must_change_password: bool = Field(
        description="True while a temporary password must be replaced before anything else."
    )


class ClientOut(ApiModel):
    id: uuid.UUID
    name: str
    email: str
    phone: str
    company: str | None
    is_sample: bool


CLIENT_NAME_MESSAGE = "Enter the client's name (at least 2 characters)."
CLIENT_EMAIL_MESSAGE = "Enter an e-mail address such as name@example.com."
CLIENT_PHONE_MESSAGE = "Enter a phone number: digits, spaces, +, - or brackets (7 to 20)."
CLIENT_TEXT_TOO_LONG = "Keep this under 201 characters."
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_PHONE = re.compile(r"\+?[0-9 ()\-]{7,20}")


def _check_client_name(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) < 2:
        raise ValueError(CLIENT_NAME_MESSAGE)
    if len(value) > 200:
        raise ValueError(CLIENT_TEXT_TOO_LONG)
    return value


def _check_client_email(value: str | None) -> str | None:
    if value is not None and (len(value) > 254 or not _EMAIL.fullmatch(value)):
        raise ValueError(CLIENT_EMAIL_MESSAGE)
    return value


def _check_client_phone(value: str | None) -> str | None:
    if value is not None and not _PHONE.fullmatch(value):
        raise ValueError(CLIENT_PHONE_MESSAGE)
    return value


def _check_company(value: str | None) -> str | None:
    if value is not None and len(value) > 200:
        raise ValueError(CLIENT_TEXT_TOO_LONG)
    return value


class ClientIn(InputModel):
    """A new client. Name, e-mail and phone are required; the company is optional."""

    name: str
    email: str
    phone: str
    company: str | None = None

    _name = field_validator("name")(_check_client_name)
    _email = field_validator("email")(_check_client_email)
    _phone = field_validator("phone")(_check_client_phone)

    @field_validator("company", mode="before")
    @classmethod
    def _blank_company(cls, value: Any) -> Any:
        return _clean_optional(value)

    _company = field_validator("company")(_check_company)


class ClientUpdate(InputModel):
    """Change a client's details. Only the fields present change; ``company`` may be null."""

    name: str | None = None
    email: str | None = None
    phone: str | None = None
    company: str | None = None

    @field_validator("name", "email", "phone", mode="before")
    @classmethod
    def _required_not_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError(NOT_EMPTY)
        return value

    _name = field_validator("name")(_check_client_name)
    _email = field_validator("email")(_check_client_email)
    _phone = field_validator("phone")(_check_client_phone)

    @field_validator("company", mode="before")
    @classmethod
    def _blank_company(cls, value: Any) -> Any:
        return _clean_optional(value)

    _company = field_validator("company")(_check_company)


class AdminUserOut(ApiModel):
    """An account as administrators see it. Never includes password or session details."""

    id: uuid.UUID
    name: str
    email: str | None
    role: UserRole
    client_id: uuid.UUID | None
    client_name: str | None = Field(description="For Client accounts: the client represented.")
    is_active: bool
    is_locked: bool = Field(description="Locked after repeated failed sign-ins.")
    can_sign_in: bool = Field(description="False until a password has been set.")
    must_change_password: bool
    last_login_at: datetime | None
    is_sample: bool


def _strip(value: Any) -> Any:
    return value.strip() if isinstance(value, str) else value


ACCOUNT_NAME_MESSAGE = "Enter the person's name (2 to 200 characters)."


def _check_account_name(value: str | None) -> str | None:
    if value is not None and not 2 <= len(value) <= 200:
        raise ValueError(ACCOUNT_NAME_MESSAGE)
    return value


class AdminUserCreate(SecretInputModel):
    """A new account with a temporary password the person must replace at first sign-in."""

    name: str
    email: str
    role: UserRole
    client_id: uuid.UUID | None = Field(default=None, description="Required for Client accounts.")
    temporary_password: str = Field(max_length=1024)

    @field_validator("name", "email", mode="before")
    @classmethod
    def _strip_text(cls, value: Any) -> Any:
        return _strip(value)

    _name = field_validator("name")(_check_account_name)
    _email = field_validator("email")(_check_client_email)


class AdminUserUpdate(InputModel):
    """Change an account's name or e-mail address (the role cannot change)."""

    name: str | None = None
    email: str | None = None

    @field_validator("name", "email", mode="before")
    @classmethod
    def _required_not_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError(NOT_EMPTY)
        return value

    _name = field_validator("name")(_check_account_name)
    _email = field_validator("email")(_check_client_email)


class TemporaryPasswordIn(SecretInputModel):
    temporary_password: str = Field(max_length=1024)


class AuditEventOut(ApiModel):
    """One audit-log entry. ``details`` holds only whitelisted, non-secret values."""

    id: uuid.UUID
    occurred_at: datetime
    actor_id: uuid.UUID | None
    actor_name: str | None = Field(description="As it was when the event happened.")
    actor_role: str | None
    action: str
    outcome: AuditOutcome
    target_type: str | None
    target_id: uuid.UUID | None
    case_id: uuid.UUID | None
    case_number: str | None
    details: dict[str, Any]


class AuditPage(ApiModel):
    events: list[AuditEventOut]
    next_before: uuid.UUID | None = Field(
        description="Pass as ``before`` for the next (older) page; null on the last page."
    )


class ClientOption(ApiModel):
    """A client as offered in the new-case form: no contact details."""

    id: uuid.UUID
    name: str
    is_sample: bool


class AdvocateOut(ApiModel):
    id: uuid.UUID
    name: str
    email: str | None
    is_sample: bool


# --- cases ----------------------------------------------------------------------


class HearingOut(ApiModel):
    id: uuid.UUID
    date: date
    time: str | None = Field(description="24-hour HH:MM, or null until the court lists it.")
    court: str
    purpose: str
    status: HearingStatus = Field(
        description="Cancelled hearings are kept but are never the next or an upcoming hearing."
    )
    cancellation_reason: str | None
    is_sample: bool


class UpcomingHearingOut(HearingOut):
    case_id: uuid.UUID
    case_title: str
    case_number: str


class ScheduledHearingOut(UpcomingHearingOut):
    lead_attorney: str = Field(description="Name of the case's lead advocate.")


class HearingSchedule(ApiModel):
    """Hearings in a date range, soonest first."""

    hearings: list[ScheduledHearingOut]
    truncated: bool = Field(description="True when more hearings matched than the limit.")


class PortalHearingOut(ApiModel):
    """A scheduled hearing as the client sees it."""

    date: date
    time: str | None
    court: str
    purpose: str


class PortalDocumentOut(ApiModel):
    """A document shared with the client."""

    id: uuid.UUID
    name: str
    type: str
    size: str
    shared_on: date
    download_url: str


class PortalCaseSummary(ApiModel):
    """A case as its client sees it: no internal notes, priority or team."""

    id: uuid.UUID
    case_number: str
    title: str
    status: CaseStatus
    practice_area: PracticeArea
    lead_attorney: str
    court_name: str | None
    opened_on: date
    next_hearing: date | None


class PortalCaseDetail(PortalCaseSummary):
    hearings: list[PortalHearingOut] = Field(description="Scheduled hearings from today on.")
    documents: list[PortalDocumentOut] = Field(description="Documents shared with you.")


class ActorOut(ApiModel):
    id: uuid.UUID
    name: str


class TimelineEventOut(ApiModel):
    id: uuid.UUID
    date: date
    label: str
    description: str
    actor: ActorOut | None = Field(
        description="Who made the change. Null for sample entries and changes made by the system."
    )
    recorded_at: datetime = Field(description="When the entry was recorded (UTC).")
    is_sample: bool


class DocumentProcessingOut(ApiModel):
    """Text extraction of a stored document (Phase 3)."""

    status: ExtractionStatus = Field(
        description="queued, processing, ready, failed (with a reason) or unsupported."
    )
    reason_code: str | None = Field(description="Why it failed or is unsupported.")
    reason: str | None
    page_count: int | None = Field(description="PDFs only; null for documents without pages.")
    section_count: int | None = Field(description="Pages, or parts of a document without pages.")
    chunk_count: int | None
    index_status: IndexStatus = Field(
        description="Search indexing (embeddings): disabled unless configured."
    )
    updated_at: datetime


class DocumentTextSectionOut(ApiModel):
    number: int = Field(description="1 to sectionCount.")
    page_number: int | None = Field(description="The PDF page; null for documents without pages.")
    text: str = Field(description="Exactly as extracted; may be empty for a page without text.")
    chunk_count: int


class DocumentTextOut(ApiModel):
    """One page (or part) of a document's extracted text."""

    document_id: uuid.UUID
    document_name: str
    extractor: str | None = Field(description="What extracted the text, e.g. 'pypdf 6.21.1'.")
    page_count: int | None = Field(description="PDFs only; null for documents without pages.")
    section_count: int
    char_count: int
    extracted_at: datetime | None
    section: DocumentTextSectionOut


class CaseSearchHitOut(ApiModel):
    """A passage of one of the case's documents, located exactly."""

    document_id: uuid.UUID
    document_name: str
    chunk_id: uuid.UUID
    chunk_number: int
    section_number: int = Field(description="The page (PDF) or part the passage is in.")
    page_number: int | None = Field(description="The PDF page; null for documents without pages.")
    char_start: int = Field(description="Offset of the passage in the section's extracted text.")
    char_end: int
    text: str = Field(description="The passage, exactly as extracted.")
    score: float = Field(
        description="Ranking score of the mode: cosine similarity (semantic), full-text rank "
        "(keyword) or reciprocal-rank fusion (hybrid). Higher is closer; not a probability."
    )


class CaseSearchOut(ApiModel):
    """Passages of the case's own documents ranked against the query (no legal judgment)."""

    mode: Literal["keyword", "semantic", "hybrid"]
    model: str | None = Field(description="The embedding model (semantic and hybrid modes).")
    documents_with_text: int = Field(description="Live documents of the case whose text is ready.")
    documents_indexed: int = Field(
        description="Of those, how many have vectors for the model (semantic and hybrid)."
    )
    results: list[CaseSearchHitOut]


class DocumentOut(ApiModel):
    id: uuid.UUID
    name: str
    type: str
    uploaded_on: date
    size: str = Field(description="Human-readable size, e.g. '512 KB'.")
    size_bytes: int | None = Field(description="Exact size of the stored file; null without one.")
    has_file: bool = Field(description="False for sample records, which have no stored file.")
    content_type: str | None
    download_url: str | None
    uploaded_by: ActorOut | None = Field(
        description="Who uploaded it; null for sample records and earlier uploads."
    )
    shared_with_client_at: datetime | None = Field(
        description="When it was shared with the client (their portal shows it); null if not."
    )
    processing: DocumentProcessingOut | None = Field(
        description="Text extraction; null for records without a stored file."
    )
    is_sample: bool


class DeletedDocumentOut(DocumentOut):
    """A deleted document, kept until restored or purged by an operator."""

    deleted_at: datetime
    deleted_by: ActorOut | None = Field(description="Who deleted it, if still known.")


class CaseSummary(ApiModel):
    id: uuid.UUID
    case_number: str
    title: str
    status: CaseStatus
    priority: CasePriority
    practice_area: PracticeArea
    client_id: uuid.UUID
    client_name: str
    lead_advocate_id: uuid.UUID
    lead_attorney: str = Field(description="Name of the lead advocate.")
    court_name: str | None
    opposing_party: str | None
    opened_on: date
    next_hearing: date | None = Field(
        description=(
            "Earliest hearing on or after today; if none, the most recent past one "
            "(so the client can show it has passed). Derived from the hearings."
        )
    )
    document_count: int
    archived_at: datetime | None = Field(
        description="When the case was archived (read-only until restored); null if active."
    )
    is_sample: bool


class CasePermissions(ApiModel):
    """What the signed-in user may do on this case (to show the right controls).

    A convenience for the screens only: the server checks every action again.
    """

    relation: Literal["admin", "lead", "associate", "paralegal", "client", "none"]
    editable_fields: list[str] = Field(description="Fields this user may change (camelCase).")
    can_change_status: bool
    can_manage_team: bool
    can_archive: bool
    can_manage_hearings: bool
    can_upload_documents: bool
    can_delete_documents: bool
    can_restore_documents: bool
    can_share_documents: bool


class TeamMemberOut(ApiModel):
    """Someone on a case team besides the lead advocate."""

    id: uuid.UUID
    name: str
    role: UserRole
    member_role: Literal["associate", "paralegal"]


class StaffOut(ApiModel):
    """An active staff member, as offered when building a case team."""

    id: uuid.UUID
    name: str
    role: UserRole


TIME_MESSAGE = "Enter the time as HH:MM (24-hour), or leave it blank."
COURT_MESSAGE = "Enter the court or forum."
PURPOSE_MESSAGE = "Enter the purpose of the hearing."
HEARING_TEXT_TOO_LONG = f"Keep this under {HEARING_TEXT_MAX + 1} characters."
REASON_TOO_LONG = f"Keep the reason under {CANCELLATION_REASON_MAX + 1} characters."
_TIME = re.compile(r"([01]\d|2[0-3]):[0-5]\d")


def _check_time(value: str | None) -> str | None:
    if value is not None and not _TIME.fullmatch(value):
        raise ValueError(TIME_MESSAGE)
    return value


def _check_hearing_text(value: str | None, empty_message: str) -> str | None:
    if value is None:
        return None
    if not value:
        raise ValueError(empty_message)
    if len(value) > HEARING_TEXT_MAX:
        raise ValueError(HEARING_TEXT_TOO_LONG)
    return value


class HearingIn(InputModel):
    """Schedule a hearing. The time may be left out until the court lists it."""

    date: date
    time: str | None = Field(default=None, description="24-hour HH:MM, or omitted.")
    court: str
    purpose: str

    @field_validator("time", mode="before")
    @classmethod
    def _blank_time(cls, value: Any) -> Any:
        return _clean_optional(value)

    @field_validator("time")
    @classmethod
    def _time(cls, value: str | None) -> str | None:
        return _check_time(value)

    @field_validator("court")
    @classmethod
    def _court(cls, value: str) -> str | None:
        return _check_hearing_text(value, COURT_MESSAGE)

    @field_validator("purpose")
    @classmethod
    def _purpose(cls, value: str) -> str | None:
        return _check_hearing_text(value, PURPOSE_MESSAGE)


# A field named ``date`` with a default would hide the type inside the class body.
_Date = date


class HearingUpdate(InputModel):
    """Change a scheduled hearing. Only the fields present change; ``time`` may be null."""

    date: _Date | None = None
    time: str | None = None
    court: str | None = None
    purpose: str | None = None

    @field_validator("date", "court", "purpose", mode="before")
    @classmethod
    def _required_not_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError(NOT_EMPTY)
        return value

    @field_validator("time", mode="before")
    @classmethod
    def _blank_time(cls, value: Any) -> Any:
        return _clean_optional(value)

    @field_validator("time")
    @classmethod
    def _time(cls, value: str | None) -> str | None:
        return _check_time(value)

    @field_validator("court")
    @classmethod
    def _court(cls, value: str | None) -> str | None:
        return _check_hearing_text(value, COURT_MESSAGE)

    @field_validator("purpose")
    @classmethod
    def _purpose(cls, value: str | None) -> str | None:
        return _check_hearing_text(value, PURPOSE_MESSAGE)


class HearingCancelIn(InputModel):
    reason: str | None = Field(default=None, description="Optional, shown on the case.")

    @field_validator("reason", mode="before")
    @classmethod
    def _blank(cls, value: Any) -> Any:
        return _clean_optional(value)

    @field_validator("reason")
    @classmethod
    def _length(cls, value: str | None) -> str | None:
        if value is not None and len(value) > CANCELLATION_REASON_MAX:
            raise ValueError(REASON_TOO_LONG)
        return value


class TeamMemberIn(InputModel):
    user_id: uuid.UUID = Field(description="An active Advocate (associate) or Paralegal.")


class ClientDetail(ClientOut):
    cases: list[CaseSummary] = Field(description="The client's cases that you may see.")
    can_edit: bool = Field(description="Whether you may change these details.")


class CaseDetail(CaseSummary):
    description: str
    documents: list[DocumentOut]
    hearings: list[HearingOut]
    timeline: list[TimelineEventOut]
    team: list[TeamMemberOut]
    permissions: CasePermissions


def _clean_optional(value: Any) -> Any:
    """Optional text: surrounding space removed, empty means absent."""
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _check_title(value: str) -> str:
    if len(value) < TITLE_MIN:
        raise ValueError(TITLE_MESSAGE)
    if len(value) > TITLE_MAX:
        raise ValueError(TITLE_TOO_LONG)
    return value


def _check_description(value: str) -> str:
    if len(value) < DESCRIPTION_MIN:
        raise ValueError(DESCRIPTION_MESSAGE)
    if len(value) > DESCRIPTION_MAX:
        raise ValueError(DESCRIPTION_TOO_LONG)
    return value


def _check_short(value: str | None) -> str | None:
    if value is not None and len(value) > SHORT_TEXT_MAX:
        raise ValueError(SHORT_TEXT_TOO_LONG)
    return value


class CaseCreate(InputModel):
    title: str
    client_id: uuid.UUID
    practice_area: PracticeArea
    status: CaseStatus
    priority: CasePriority
    lead_advocate_id: uuid.UUID
    court_name: str | None = None
    opposing_party: str | None = None
    description: str
    next_hearing: date | None = Field(
        default=None, description="Creates the first hearing. Cannot be in the past."
    )

    _title = field_validator("title")(_check_title)
    _description = field_validator("description")(_check_description)

    @field_validator("court_name", "opposing_party", mode="before")
    @classmethod
    def _optional_text(cls, value: Any) -> Any:
        return _clean_optional(value)

    @field_validator("court_name", "opposing_party")
    @classmethod
    def _short(cls, value: str | None) -> str | None:
        return _check_short(value)


class CaseUpdate(InputModel):
    """Partial update. Only the fields present in the request change.

    ``courtName`` and ``opposingParty`` may be null to clear them; the other
    fields cannot be null.
    """

    title: str | None = None
    status: CaseStatus | None = None
    priority: CasePriority | None = None
    practice_area: PracticeArea | None = None
    client_id: uuid.UUID | None = None
    lead_advocate_id: uuid.UUID | None = None
    court_name: str | None = None
    opposing_party: str | None = None
    description: str | None = None

    @field_validator(
        "title",
        "status",
        "priority",
        "practice_area",
        "client_id",
        "lead_advocate_id",
        "description",
        mode="before",
    )
    @classmethod
    def _required_not_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError(NOT_EMPTY)
        return value

    @field_validator("title")
    @classmethod
    def _title(cls, value: str | None) -> str | None:
        return None if value is None else _check_title(value)

    @field_validator("description")
    @classmethod
    def _description(cls, value: str | None) -> str | None:
        return None if value is None else _check_description(value)

    @field_validator("court_name", "opposing_party", mode="before")
    @classmethod
    def _optional_text(cls, value: Any) -> Any:
        return _clean_optional(value)

    @field_validator("court_name", "opposing_party")
    @classmethod
    def _short(cls, value: str | None) -> str | None:
        return _check_short(value)
