"""Text extraction from stored documents (Phase 3).

Extractors turn a file's bytes into *sections*: one per PDF page, or numbered
parts of a document that has no pages (Word, text), whose ``page_number`` is
``None``. They never invent text: a file that yields no text is an error with a
reason, not an empty success.

``extract`` is called by the worker in a child process (``lexflow.extraction.runner``)
so that a pathological file can be stopped after the time limit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TXT = "text/plain"
EXTRACTABLE_TYPES = frozenset({PDF, DOCX, TXT})

# Why other stored types are not processed (status "unsupported").
UNSUPPORTED_REASONS = {
    "application/msword": (
        "Text is not extracted from old Word (.doc) files. Save it as .docx and upload it "
        "again to make its text available."
    ),
    "image": "Text is not extracted from images (OCR is not available).",
}


def unsupported_reason(content_type: str | None) -> str:
    if content_type and content_type.startswith("image/"):
        return UNSUPPORTED_REASONS["image"]
    if content_type in UNSUPPORTED_REASONS:
        return UNSUPPORTED_REASONS[content_type]
    return "Text is not extracted from this type of file."


@dataclass(frozen=True)
class Limits:
    max_pages: int
    max_text_bytes: int
    max_unpacked_bytes: int


@dataclass(frozen=True)
class Section:
    """Text of one PDF page (``page_number`` set) or one part (``page_number`` None)."""

    page_number: int | None
    text: str


@dataclass(frozen=True)
class Extracted:
    sections: list[Section]
    extractor: str  # e.g. "pypdf 6.1.3"
    page_count: int | None = None  # PDFs only

    @property
    def char_count(self) -> int:
        return sum(len(s.text) for s in self.sections)


@dataclass
class ExtractionError(Exception):
    """A file whose text cannot be extracted. ``code`` is stable; ``message`` is
    shown to people (it never contains the document's text). ``retry`` marks
    problems that may go away (anything else fails the job at once)."""

    code: str
    message: str
    retry: bool = field(default=False)

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def extract(content_type: str, data: bytes, limits: Limits) -> Extracted:
    """The text of a stored file, or ``ExtractionError``."""
    if content_type not in EXTRACTABLE_TYPES:
        raise ExtractionError("unsupported-type", unsupported_reason(content_type))
    raise ExtractionError(
        "extractor-unavailable", "Text extraction is not available in this version."
    )
