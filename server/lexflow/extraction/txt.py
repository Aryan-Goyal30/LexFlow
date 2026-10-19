"""Plain text (UTF-8, as checked on upload). No pages: numbered parts."""

from __future__ import annotations

from lexflow.extraction import (
    Extracted,
    ExtractionError,
    Limits,
    check_text_size,
    normalise,
    split_parts,
)

EXTRACTOR = "utf-8 text"


def extract_txt(data: bytes, limits: Limits) -> Extracted:
    try:
        raw = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ExtractionError("unreadable", "This text file is not valid UTF-8.") from None
    text = normalise(raw)
    check_text_size(len(text.encode("utf-8")), limits)
    if not text:
        raise ExtractionError("no-text", "This text file is empty.")
    return Extracted(sections=split_parts(text), extractor=EXTRACTOR)
