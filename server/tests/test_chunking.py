"""Page-aware chunking (no database needed)."""

from __future__ import annotations

import hashlib
import itertools

import pytest

from lexflow.extraction import Section
from lexflow.extraction.chunking import chunk_sections
from lexflow.services.extraction_queue import ChunkData

SIZE, OVERLAP = 1200, 200


def prose(paragraphs: int, seed: int = 0) -> str:
    """Fictional sentences of varied length, in paragraphs."""
    words = [
        "petition",
        "respondent",
        "agreement",
        "annexure",
        "hearing",
        "fictional",
        "evidence",
        "clause",
        "order",
        "the",
        "of",
        "and",
        "dated",
    ]
    out = []
    for p in range(paragraphs):
        sentences = []
        for s in range(3 + (p + seed) % 5):
            n = 6 + (p * 7 + s * 3 + seed) % 17
            sentences.append(
                " ".join(words[(p + s + i) % len(words)] for i in range(n)).capitalize() + "."
            )
        out.append(" ".join(sentences))
    return "\n\n".join(out)


def check_invariants(sections: list[Section], chunks: list[ChunkData], size: int) -> None:
    assert [c.number for c in chunks] == list(range(1, len(chunks) + 1))
    for chunk in chunks:
        section = sections[chunk.section_number - 1]
        assert chunk.text == section.text[chunk.char_start : chunk.char_end]
        assert chunk.page_number == section.page_number
        assert 0 < len(chunk.text) <= size
        assert chunk.text == chunk.text.strip()
        assert chunk.content_sha256 == hashlib.sha256(chunk.text.encode()).hexdigest()
    # Every non-blank character of every section is in some chunk.
    for number, section in enumerate(sections, start=1):
        covered = [False] * len(section.text)
        for chunk in chunks:
            if chunk.section_number == number:
                for i in range(chunk.char_start, chunk.char_end):
                    covered[i] = True
        missing = [i for i, ch in enumerate(section.text) if not ch.isspace() and not covered[i]]
        assert missing == [], f"section {number}: uncovered characters at {missing[:5]}"


@pytest.mark.parametrize("paragraphs", [1, 3, 12, 40])
def test_chunks_cover_the_text_exactly_within_the_size(paragraphs: int) -> None:
    sections = [Section(page_number=1, text=prose(paragraphs))]
    chunks = chunk_sections(sections, SIZE, OVERLAP)
    check_invariants(sections, chunks, SIZE)


def test_chunks_never_cross_pages_and_keep_their_page_number() -> None:
    sections = [Section(page_number=p, text=prose(6, seed=p)) for p in (1, 2, 3)]
    chunks = chunk_sections(sections, SIZE, OVERLAP)
    check_invariants(sections, chunks, SIZE)
    assert {c.page_number for c in chunks} == {1, 2, 3}
    assert all(c.page_number == c.section_number for c in chunks)


def test_documents_without_pages_keep_page_numbers_empty() -> None:
    sections = [
        Section(page_number=None, text=prose(5)),
        Section(page_number=None, text=prose(5, 2)),
    ]
    chunks = chunk_sections(sections, SIZE, OVERLAP)
    check_invariants(sections, chunks, SIZE)
    assert {c.page_number for c in chunks} == {None}
    assert {c.section_number for c in chunks} == {1, 2}


def test_empty_pages_produce_no_chunks() -> None:
    sections = [
        Section(1, "FICTIONAL first page."),
        Section(2, ""),
        Section(3, "  \n "),
        Section(4, "Last."),
    ]
    chunks = chunk_sections(sections, SIZE, OVERLAP)
    assert [(c.page_number, c.text) for c in chunks] == [(1, "FICTIONAL first page."), (4, "Last.")]


def test_consecutive_chunks_overlap_by_about_the_configured_amount() -> None:
    sections = [Section(page_number=1, text=prose(40))]
    chunks = chunk_sections(sections, SIZE, OVERLAP)
    assert len(chunks) > 3
    for previous, current in itertools.pairwise(chunks):
        shared = previous.char_end - current.char_start
        assert 0 < shared <= OVERLAP, (previous.number, shared)
        assert current.char_start > previous.char_start  # always moves forward
        # The overlap starts at a word.
        assert sections[0].text[current.char_start - 1].isspace()


def test_chunks_end_at_paragraph_or_sentence_breaks_when_possible() -> None:
    sections = [Section(page_number=1, text=prose(40))]
    chunks = chunk_sections(sections, SIZE, OVERLAP)
    for chunk in chunks[:-1]:
        assert chunk.text.endswith(".") or chunk.text[-1].isalpha(), repr(chunk.text[-20:])
    paragraph_ends = sum(
        1 for c in chunks[:-1] if sections[0].text[c.char_end : c.char_end + 2] == "\n\n"
    )
    assert paragraph_ends >= len(chunks) // 2  # mostly at paragraph breaks


def test_a_word_longer_than_a_chunk_is_cut() -> None:
    sections = [Section(page_number=1, text="x" * 3000)]
    chunks = chunk_sections(sections, SIZE, OVERLAP)
    check_invariants(sections, chunks, SIZE)
    assert len(chunks[0].text) == SIZE


def test_chunking_is_deterministic() -> None:
    sections = [Section(page_number=p, text=prose(15, seed=p)) for p in (1, 2)]
    assert chunk_sections(sections, SIZE, OVERLAP) == chunk_sections(sections, SIZE, OVERLAP)


@pytest.mark.parametrize(("size", "overlap"), [(200, 0), (500, 100), (2000, 300)])
def test_other_sizes_keep_the_invariants(size: int, overlap: int) -> None:
    sections = [Section(page_number=1, text=prose(25)), Section(page_number=2, text="Short.")]
    check_invariants(sections, chunk_sections(sections, size, overlap), size)
