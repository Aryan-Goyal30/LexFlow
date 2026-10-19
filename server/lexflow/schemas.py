"""Request and response models.

JSON uses camelCase to match the TypeScript front end (``src/types``). Python
code uses snake_case; the alias generator translates. Validation messages match
the ones the front end shows, so server errors can sit beside the right field.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from lexflow.domain import (
    DESCRIPTION_MAX,
    DESCRIPTION_MIN,
    SHORT_TEXT_MAX,
    TITLE_MAX,
    TITLE_MIN,
    CasePriority,
    CaseStatus,
    PracticeArea,
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


class ClientOut(ApiModel):
    id: uuid.UUID
    name: str
    email: str
    phone: str
    company: str | None
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
    is_sample: bool


class UpcomingHearingOut(HearingOut):
    case_id: uuid.UUID
    case_title: str
    case_number: str


class ActorOut(ApiModel):
    id: uuid.UUID
    name: str


class TimelineEventOut(ApiModel):
    id: uuid.UUID
    date: date
    label: str
    description: str
    actor: ActorOut | None = Field(
        description="Who made the change. Null when no signed-in user did (always in Phase 1)."
    )
    is_sample: bool


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
    is_sample: bool


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
    is_sample: bool


class CaseDetail(CaseSummary):
    description: str
    documents: list[DocumentOut]
    hearings: list[HearingOut]
    timeline: list[TimelineEventOut]


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
