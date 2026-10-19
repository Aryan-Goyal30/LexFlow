"""Text extraction from stored documents (Phase 3).

Extractors turn a file's bytes into *sections*: one per PDF page, or numbered
parts of a document that has no pages (Word, text), whose ``page_number`` is
``None``. They never invent text: a file that yields no text is an error with a
reason, not an empty success.

``extract`` is called by the worker in a child process (``lexflow.extraction.runner``)
so that a pathological file can be stopped after the time limit.
"""

from __future__ import annotations

import re
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


# Documents without pages are shown in parts of about this many characters,
# split at paragraph breaks where possible.
PART_CHARS = 20_000
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_TRAILING_SPACE = re.compile(r"[ \t]+\n")
_BLANK_LINES = re.compile(r"\n{3,}")


def normalise(text: str) -> str:
    """Line endings to a newline, control characters (other than tab and
    newline) removed, trailing spaces and runs of blank lines trimmed. Words are
    never changed."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")
    text = _CONTROL.sub("", text)
    text = _TRAILING_SPACE.sub("\n", text)
    return _BLANK_LINES.sub("\n\n", text).strip()


def split_parts(text: str, size: int = PART_CHARS) -> list[Section]:
    """Numbered parts of a document without pages (``page_number`` None)."""
    parts: list[Section] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            cut = text.rfind("\n\n", start + size // 2, end)
            if cut == -1:
                cut = text.rfind("\n", start + size // 2, end)
            if cut != -1:
                end = cut
        part = text[start:end].strip("\n")
        if part:
            parts.append(Section(page_number=None, text=part))
        start = end
    return parts


def check_text_size(total_bytes: int, limits: Limits) -> None:
    if total_bytes > limits.max_text_bytes:
        megabytes = limits.max_text_bytes / 1_000_000
        raise ExtractionError(
            "text-too-large",
            f"The document has more than {megabytes:g} MB of text, the processing limit.",
        )


def extract(content_type: str, data: bytes, limits: Limits) -> Extracted:
    """The text of a stored file, or ``ExtractionError``."""
    from lexflow.extraction import docx, pdf, txt

    if content_type == PDF:
        return pdf.extract_pdf(data, limits)
    if content_type == DOCX:
        return docx.extract_docx(data, limits)
    if content_type == TXT:
        return txt.extract_txt(data, limits)
    raise ExtractionError("unsupported-type", unsupported_reason(content_type))
