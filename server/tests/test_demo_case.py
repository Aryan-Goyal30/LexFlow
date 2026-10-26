"""The FICTIONAL demo case pack (Milestone 1): committed files match the builder,
every file is labelled fictional, the real extractors read each one, and every
key fact and both sides of the planted contradiction are found where the
manifest says (the right PDF page). No database, no provider."""

from __future__ import annotations

import json
import re

import pytest

from lexflow.extraction import DOCX, PDF, TXT, Extracted, Limits, extract
from tests.demo_case import (
    CASE_REF,
    CONTRADICTION,
    DEMO_DIR,
    DOCUMENTS,
    KEY_FACTS,
    NOTICE,
    manifest,
    manifest_bytes,
)

LIMITS = Limits(max_pages=100, max_text_bytes=1_000_000, max_unpacked_bytes=10_000_000)
TYPES = {".pdf": PDF, ".docx": DOCX, ".txt": TXT}


def read(name: str) -> Extracted:
    return extract(TYPES[name[name.rindex(".") :]], (DEMO_DIR / name).read_bytes(), LIMITS)


def text_on(extracted: Extracted, page: int | None) -> str:
    sections = [s for s in extracted.sections if page is None or s.page_number == page]
    return re.sub(r"\s+", " ", " ".join(s.text for s in sections))


def plain(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


@pytest.mark.parametrize("name", [d[0] for d in DOCUMENTS])
def test_the_committed_file_matches_the_builder(name: str) -> None:
    build = next(d[4] for d in DOCUMENTS if d[0] == name)
    committed = (DEMO_DIR / name).read_bytes()
    if name.endswith(".docx"):
        # Word files carry a zip timestamp: compare what a reader sees, not the bytes.
        fresh = extract(DOCX, build(), LIMITS)
        assert text_on(read(name), None) == text_on(fresh, None)
    else:
        assert committed == build()


def test_the_manifest_matches_the_builder() -> None:
    assert (DEMO_DIR / "manifest.json").read_bytes() == manifest_bytes()
    assert json.loads(manifest_bytes()) == manifest()
    listed = {d["file"] for d in manifest()["documents"]}
    on_disk = {p.name for p in DEMO_DIR.iterdir()} - {"manifest.json", "README.md"}
    assert listed == on_disk


@pytest.mark.parametrize("name", [d[0] for d in DOCUMENTS])
def test_every_document_is_labelled_fictional_and_reads_with_the_real_extractors(
    name: str,
) -> None:
    extracted = read(name)
    assert extracted.char_count > 300, "enough text to exercise chunking and search"
    if name.endswith(".pdf"):
        pages = [s.page_number for s in extracted.sections]
        assert pages == list(range(1, (extracted.page_count or 0) + 1))
        for section in extracted.sections:  # every page carries the notice
            assert NOTICE in plain(section.text) and CASE_REF in plain(section.text)
    else:
        assert NOTICE in text_on(extracted, None) and CASE_REF in text_on(extracted, None)


@pytest.mark.parametrize(("name", "page", "fact"), KEY_FACTS)
def test_each_key_fact_is_on_the_page_the_manifest_names(
    name: str, page: int | None, fact: str
) -> None:
    extracted = read(name)
    assert plain(fact) in text_on(extracted, page)
    if page is not None:  # and on no other page
        others = [s.page_number for s in extracted.sections if s.page_number != page]
        assert all(plain(fact) not in text_on(extracted, p) for p in others)


def test_the_planted_contradiction_is_in_both_documents_where_stated() -> None:
    affidavit, ledger = CONTRADICTION["statements"]
    assert plain(affidavit["text"]) in text_on(read(affidavit["file"]), affidavit["page"])
    assert plain(ledger["text"]) in text_on(read(ledger["file"]), ledger["page"])
    # The two documents give different dates for the same invoice.
    assert "14 March 2016" in affidavit["text"] and "VF/INV/0001" in text_on(
        read(affidavit["file"]), 1
    )
    assert "2 August 2017" in ledger["text"] and "VF/INV/0001" in ledger["text"]
    for item in CONTRADICTION["also_pleaded"]:
        assert plain(item["text"]) in text_on(read(item["file"]), item["page"])


def test_no_real_court_or_registry_is_named_without_a_fictional_label() -> None:
    for name, *_ in DOCUMENTS:
        text = text_on(read(name), None)
        for line in re.split(r"(?<=[.;])\s", text):
            if (
                re.search(r"\b(Court|High Court|Registry)\b", line)
                and "Trade Marks Act" not in line
            ):
                assert re.search(r"(?i)fictional", line), (name, line)
