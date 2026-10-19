"""Fictional documents for the extraction tests, built in code.

Everything here is invented for tests: the parties, case numbers and text are
not real. The PDF builder writes small, valid PDFs whose text layer is known
exactly, so tests can check the extracted text page by page. Output is
deterministic (no timestamps or random ids), so the committed copies in
``tests/fixtures/documents/`` can be checked against it.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Callable
from pathlib import Path

import docx

# Text of the multi-page fixture, one string per page (FICTIONAL).
SAMPLE_PAGES = [
    "FICTIONAL TEST DOCUMENT - not a real matter.\n"
    "In the High Court of Example (fictional)\n"
    "Petition No. TEST-001 of 2026\n"
    "Page one: the petitioner Asha Testcase states the facts of the dispute.",
    "Page two: the respondent Example Traders replied on 3 March 2026.\n"
    "The agreement dated 1 January 2026 is annexed as Annexure T-1.",
    "Page three: prayer for relief and verification.\nSigned for testing purposes only.",
]


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf(page_streams: list[bytes]) -> bytes:
    """A minimal PDF: catalog, pages, one font, one content stream per page."""
    objects: list[bytes] = []
    count = len(page_streams)
    page_ids = [4 + 2 * i for i in range(count)]
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{pid} 0 R" for pid in page_ids).encode()
    objects.append(b"<< /Type /Pages /Kids [" + kids + b"] /Count " + str(count).encode() + b" >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for i, stream in enumerate(page_streams):
        content_id = page_ids[i] + 1
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents "
            + str(content_id).encode()
            + b" 0 R >>"
        )
        objects.append(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    ).encode()
    return bytes(out)


def _text_stream(text: str) -> bytes:
    lines = text.split("\n")
    ops = ["BT", "/F1 11 Tf", "14 TL", "72 740 Td"]
    for index, line in enumerate(lines):
        if index:
            ops.append("T*")
        ops.append(f"({_escape(line)}) Tj")
    ops.append("ET")
    return "\n".join(ops).encode("latin-1")


def pdf_with_pages(pages: list[str]) -> bytes:
    """A PDF with one page per string, each page's text drawn as real text."""
    return _pdf([_text_stream(page) for page in pages])


def pdf_without_text(pages: int = 2) -> bytes:
    """A PDF whose pages only have drawings (like a scan): no text layer."""
    drawing = b"0.5 g 72 600 300 100 re f"
    return _pdf([drawing] * pages)


def pdf_with_a_blank_page() -> bytes:
    """Three pages; the middle one has no text."""
    return _pdf(
        [
            _text_stream("FICTIONAL. First page text."),
            b"0.5 g 72 600 300 100 re f",
            _text_stream("FICTIONAL. Third page text."),
        ]
    )


def encrypted_pdf(password: str = "fictional-test-password") -> bytes:  # noqa: S107 - fixture
    """A PDF that needs a password to open (not deterministic: random ids)."""
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for page in PdfReader(io.BytesIO(pdf_with_pages(["FICTIONAL secret page."]))).pages:
        writer.add_page(page)
    writer.encrypt(user_password=password, owner_password=password, algorithm="RC4-128")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def damaged_pdf() -> bytes:
    return b"%PDF-1.4\n1 0 obj << /Type /Catalog /Pages 9 0 R >> endobj\ngarbage\n%%EOF\n"


def docx_with(paragraphs: list[str], table: list[list[str]] | None = None) -> bytes:
    document = docx.Document()
    for text in paragraphs:
        document.add_paragraph(text)
    if table:
        grid = document.add_table(rows=len(table), cols=len(table[0]))
        for r, row in enumerate(table):
            for c, value in enumerate(row):
                grid.cell(r, c).text = value
    document.add_paragraph("FICTIONAL - end of test document.")
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


def docx_bomb(unpacked_bytes: int) -> bytes:
    """A small ZIP that declares a huge entry (all zeros compress very well)."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", b"\0" * unpacked_bytes)
    return out.getvalue()


def text_file(text: str) -> bytes:
    return text.encode("utf-8")


# The committed copies (for the end-to-end tests), written by
# scripts/make_document_fixtures.py and checked by tests/test_extractors.py.
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "documents"
FIXTURE_FILES: dict[str, Callable[[], bytes]] = {
    "fictional-petition-3-pages.pdf": lambda: pdf_with_pages(SAMPLE_PAGES),
    "fictional-scan-no-text.pdf": lambda: pdf_without_text(2),
    "fictional-notes.txt": lambda: text_file(
        "FICTIONAL TEST NOTES - not a real matter.\n\nMeeting notes for test case TEST-001.\n"
    ),
}
