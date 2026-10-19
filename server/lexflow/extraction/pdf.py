"""PDF text, page by page (pypdf, BSD licence).

Each page becomes a section with its real page number, including pages
without text (scanned pages), so page numbers stay true. A PDF with no text on
any page is an error ("no text layer"): there is no OCR in Phase 3.
"""

from __future__ import annotations

from io import BytesIO

import pypdf
from pypdf.errors import DependencyError, FileNotDecryptedError

from lexflow.extraction import (
    Extracted,
    ExtractionError,
    Limits,
    Section,
    check_text_size,
    normalise,
)

EXTRACTOR = f"pypdf {pypdf.__version__}"


def _encrypted() -> ExtractionError:
    return ExtractionError(
        "encrypted",
        "This PDF is password-protected, so its text cannot be extracted. Upload a copy "
        "without a password.",
    )


def _unreadable() -> ExtractionError:
    return ExtractionError(
        "unreadable", "This PDF is damaged or not a valid PDF, so its text cannot be read."
    )


def extract_pdf(data: bytes, limits: Limits) -> Extracted:
    try:
        reader = pypdf.PdfReader(BytesIO(data))
        if reader.is_encrypted:
            # Many PDFs are "encrypted" only to restrict printing or copying,
            # with an empty password for reading; anything else is refused.
            try:
                if not reader.decrypt(""):
                    raise _encrypted()
            except (DependencyError, FileNotDecryptedError, NotImplementedError):
                raise _encrypted() from None
        page_count = len(reader.pages)
    except ExtractionError:
        raise
    except Exception:  # pypdf raises many kinds of errors on damaged files
        raise _unreadable() from None

    if page_count == 0:
        raise ExtractionError("no-text", "This PDF has no pages.")
    if page_count > limits.max_pages:
        raise ExtractionError(
            "too-many-pages",
            f"This PDF has {page_count} pages; the processing limit is {limits.max_pages}.",
        )

    sections: list[Section] = []
    total = 0
    for number in range(1, page_count + 1):
        try:
            text = normalise(reader.pages[number - 1].extract_text() or "")
        except ExtractionError:
            raise
        except Exception:
            raise ExtractionError(
                "unreadable", f"Page {number} of this PDF is damaged, so its text cannot be read."
            ) from None
        total += len(text.encode("utf-8"))
        check_text_size(total, limits)
        sections.append(Section(page_number=number, text=text))

    if not any(s.text for s in sections):
        raise ExtractionError(
            "no-text-layer",
            "This PDF has no text layer (it may be a scan). Text cannot be extracted from "
            "images because OCR is not available.",
        )
    return Extracted(sections=sections, extractor=EXTRACTOR, page_count=page_count)
