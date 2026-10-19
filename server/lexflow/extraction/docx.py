"""Word (.docx) text (python-docx, MIT licence).

The body's paragraphs and tables, in document order. A .docx has no fixed
pages (pagination depends on the program showing it), so the text is split
into numbered parts and ``page_number`` stays null. Headers, footers, comments
and footnotes are not included.

A .docx is a ZIP archive: before parsing, the archive's declared contents are
checked against a size limit, so a small file cannot unpack into gigabytes.
"""

from __future__ import annotations

import zipfile
from importlib.metadata import version
from io import BytesIO

import docx
from docx.document import Document as DocumentObject
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from lexflow.extraction import (
    Extracted,
    ExtractionError,
    Limits,
    check_text_size,
    normalise,
    split_parts,
)

EXTRACTOR = f"python-docx {version('python-docx')}"
MAX_ENTRIES = 10_000


def _unreadable() -> ExtractionError:
    return ExtractionError(
        "unreadable", "This Word file is damaged or not a valid .docx, so its text cannot be read."
    )


def _check_archive(data: bytes, limits: Limits) -> None:
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
    except (zipfile.BadZipFile, OSError, ValueError):
        raise _unreadable() from None
    unpacked = sum(entry.file_size for entry in entries)
    if len(entries) > MAX_ENTRIES or unpacked > limits.max_unpacked_bytes:
        raise ExtractionError(
            "too-large-unpacked",
            "This Word file would unpack to more than the processing limit, so it was not "
            "processed.",
        )


def _body_text(document: DocumentObject) -> str:
    blocks: list[str] = []
    for element in document.element.body.iterchildren():
        if element.tag == qn("w:p"):
            blocks.append(Paragraph(element, document).text)
        elif element.tag == qn("w:tbl"):
            for row in Table(element, document).rows:
                cells: list[str] = []
                for cell in row.cells:
                    text = cell.text.strip()
                    # Merged cells repeat; keep each once per row.
                    if text and (not cells or cells[-1] != text):
                        cells.append(text)
                if cells:
                    blocks.append("\t".join(cells))
    return "\n".join(blocks)


def extract_docx(data: bytes, limits: Limits) -> Extracted:
    _check_archive(data, limits)
    try:
        text = normalise(_body_text(docx.Document(BytesIO(data))))
    except ExtractionError:
        raise
    except Exception:  # python-docx and lxml raise many kinds of errors
        raise _unreadable() from None
    check_text_size(len(text.encode("utf-8")), limits)
    if not text:
        raise ExtractionError("no-text", "This Word file contains no text.")
    return Extracted(sections=split_parts(text), extractor=EXTRACTOR)
