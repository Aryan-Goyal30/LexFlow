"""Text extraction from PDF, Word and text files (no database needed).

All documents are fictional and built in ``tests/document_fixtures.py``.
"""

from __future__ import annotations

import io
import time
import zipfile

import pytest

from lexflow.extraction import (
    DOCX,
    PDF,
    TXT,
    ExtractionError,
    Limits,
    extract,
    normalise,
    split_parts,
)
from lexflow.extraction.runner import run_extraction
from tests import extraction_targets
from tests.document_fixtures import (
    FIXTURE_DIR,
    FIXTURE_FILES,
    SAMPLE_PAGES,
    damaged_pdf,
    docx_bomb,
    docx_with,
    encrypted_pdf,
    pdf_with_a_blank_page,
    pdf_with_pages,
    pdf_without_text,
)

LIMITS = Limits(max_pages=1000, max_text_bytes=5_000_000, max_unpacked_bytes=200_000_000)


def failure(content_type: str, data: bytes, limits: Limits = LIMITS) -> ExtractionError:
    with pytest.raises(ExtractionError) as caught:
        extract(content_type, data, limits)
    return caught.value


# --- PDF -------------------------------------------------------------------------------


def test_a_multi_page_pdf_keeps_each_pages_text_and_number() -> None:
    result = extract(PDF, pdf_with_pages(SAMPLE_PAGES), LIMITS)
    assert result.page_count == 3
    assert [s.page_number for s in result.sections] == [1, 2, 3]
    assert [s.text for s in result.sections] == SAMPLE_PAGES
    assert result.extractor.startswith("pypdf ")


def test_a_page_without_text_keeps_its_place() -> None:
    result = extract(PDF, pdf_with_a_blank_page(), LIMITS)
    assert [(s.page_number, bool(s.text)) for s in result.sections] == [
        (1, True),
        (2, False),
        (3, True),
    ]


def test_a_pdf_without_a_text_layer_fails_with_the_reason() -> None:
    error = failure(PDF, pdf_without_text(2))
    assert error.code == "no-text-layer"
    assert "OCR is not available" in error.message
    assert error.retry is False


def test_a_password_protected_pdf_is_refused() -> None:
    error = failure(PDF, encrypted_pdf())
    assert error.code == "encrypted"
    assert "password" in error.message


def test_a_pdf_restricted_only_by_an_owner_password_is_read() -> None:
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for page in PdfReader(io.BytesIO(pdf_with_pages(["FICTIONAL owner-only page."]))).pages:
        writer.add_page(page)
    writer.encrypt(user_password="", owner_password="fictional-owner", algorithm="RC4-128")
    out = io.BytesIO()
    writer.write(out)
    assert [s.text for s in extract(PDF, out.getvalue(), LIMITS).sections] == [
        "FICTIONAL owner-only page."
    ]


def test_a_damaged_pdf_is_unreadable() -> None:
    for data in (damaged_pdf(), b"%PDF-1.4\n", b"not a pdf at all"):
        assert failure(PDF, data).code == "unreadable"


def test_page_and_text_limits_are_enforced() -> None:
    too_many = failure(PDF, pdf_with_pages(SAMPLE_PAGES), Limits(2, 5_000_000, 200_000_000))
    assert too_many.code == "too-many-pages"
    assert "3 pages" in too_many.message and "limit is 2" in too_many.message
    too_much = failure(PDF, pdf_with_pages(SAMPLE_PAGES), Limits(1000, 100, 200_000_000))
    assert too_much.code == "text-too-large"


# --- Word ----------------------------------------------------------------------------


def test_word_paragraphs_and_tables_in_order_without_page_numbers() -> None:
    data = docx_with(
        ["FICTIONAL agreement between Asha Testcase and Example Traders.", "Clause 2."],
        table=[["Item", "Amount"], ["Fee", "100"]],
    )
    result = extract(DOCX, data, LIMITS)
    assert result.page_count is None
    assert [s.page_number for s in result.sections] == [None]
    assert result.sections[0].text == (
        "FICTIONAL agreement between Asha Testcase and Example Traders.\nClause 2.\n"
        "Item\tAmount\nFee\t100\nFICTIONAL - end of test document."
    )
    assert result.extractor.startswith("python-docx ")


def test_a_long_word_document_is_split_into_numbered_parts() -> None:
    paragraphs = [f"FICTIONAL paragraph {i}. " + "Text. " * 150 for i in range(60)]
    result = extract(DOCX, docx_with(paragraphs), LIMITS)
    assert len(result.sections) > 1
    assert all(s.page_number is None for s in result.sections)
    assert all(len(s.text) <= 20_000 for s in result.sections)
    joined = "\n".join(s.text for s in result.sections)
    for i in range(60):
        assert f"FICTIONAL paragraph {i}. " in joined  # nothing lost between parts


def test_a_word_file_that_would_unpack_too_far_is_refused_before_parsing() -> None:
    error = failure(DOCX, docx_bomb(300_000_000))
    assert error.code == "too-large-unpacked"
    small_limit = Limits(1000, 5_000_000, max_unpacked_bytes=1_000)
    assert failure(DOCX, docx_with(["FICTIONAL."]), small_limit).code == "too-large-unpacked"


def test_damaged_and_empty_word_files() -> None:
    assert failure(DOCX, b"PK\x03\x04 broken").code == "unreadable"
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
    assert failure(DOCX, out.getvalue()).code == "unreadable"  # no document part
    import docx

    empty = io.BytesIO()
    docx.Document().save(empty)
    assert failure(DOCX, empty.getvalue()).code == "no-text"


# --- text ----------------------------------------------------------------------------


def test_text_files_are_normalised_but_words_are_kept() -> None:
    result = extract(TXT, "﻿FICTIONAL line one\r\nline two  \r\n\r\n\r\n\r\nend".encode(), LIMITS)
    assert [(s.page_number, s.text) for s in result.sections] == [
        (None, "FICTIONAL line one\nline two\n\nend")
    ]


def test_empty_or_invalid_text_files_fail() -> None:
    assert failure(TXT, b" \n\t\n").code == "no-text"
    assert failure(TXT, b"\xff\xfe broken").code == "unreadable"


def test_other_types_are_unsupported() -> None:
    assert failure("image/png", b"\x89PNG").code == "unsupported-type"
    assert failure("application/msword", b"\xd0\xcf").code == "unsupported-type"


def test_normalise_only_removes_control_characters_and_extra_blank_lines() -> None:
    assert normalise("a\x00b\x07c\td\r\ne\f\n\n\n\nf  ") == "abc\td\ne\n\nf"


def test_parts_never_cut_inside_a_paragraph_when_they_can_avoid_it() -> None:
    text = "\n\n".join(f"Paragraph {i} " + "x" * 80 for i in range(40))
    parts = split_parts(text, size=500)
    assert all(p.text.startswith("Paragraph ") for p in parts)
    assert "\n\n".join(p.text for p in parts) == text


# --- the child process ----------------------------------------------------------------


def test_extraction_in_a_child_process_returns_the_same_text() -> None:
    data = pdf_with_pages(SAMPLE_PAGES)
    result = run_extraction(PDF, data, LIMITS, timeout_seconds=60)
    assert result == extract(PDF, data, LIMITS)


def test_errors_cross_from_the_child_unchanged() -> None:
    with pytest.raises(ExtractionError) as caught:
        run_extraction(PDF, pdf_without_text(1), LIMITS, timeout_seconds=60)
    assert caught.value.code == "no-text-layer"


def test_a_slow_extraction_is_stopped_at_the_time_limit() -> None:
    started = time.monotonic()
    with pytest.raises(ExtractionError) as caught:
        run_extraction(TXT, b"x", LIMITS, timeout_seconds=2, target=extraction_targets.sleeps)
    assert caught.value.code == "timed-out"
    assert caught.value.retry is False
    assert time.monotonic() - started < 30  # stopped, not waited out


def test_a_crashed_extraction_is_reported_and_may_be_retried() -> None:
    with pytest.raises(ExtractionError) as caught:
        run_extraction(TXT, b"x", LIMITS, timeout_seconds=60, target=extraction_targets.crashes)
    assert (caught.value.code, caught.value.retry) == ("extractor-crashed", True)


def test_an_extractor_bug_reveals_no_details() -> None:
    with pytest.raises(ExtractionError) as caught:
        run_extraction(
            TXT,
            b"FICTIONAL secret",
            LIMITS,
            timeout_seconds=60,
            target=extraction_targets.has_a_bug,
        )
    assert caught.value.code == "extractor-error"
    assert "secret" not in caught.value.message and "internal" not in caught.value.message


# --- committed fixtures ---------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(FIXTURE_FILES))
def test_committed_fixtures_match_the_builder(name: str) -> None:
    assert (FIXTURE_DIR / name).read_bytes() == FIXTURE_FILES[name](), name
