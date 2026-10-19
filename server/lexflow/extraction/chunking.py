"""Split extracted sections into overlapping, page-aware chunks.

- Chunks never cross a section, so each has exactly one page number (or none
  for documents without pages): later citations point at one page.
- ``text`` is always exactly ``section_text[char_start:char_end]``; offsets can
  be checked against the stored section.
- A chunk ends at the best break before the size limit: a blank line, then a
  line break, then the end of a sentence, then a space. Only a single "word"
  longer than the limit is cut mid-word.
- The next chunk starts about ``overlap`` characters before the previous one
  ended, at the start of a word, so context carries over.
- Deterministic: the same sections always give the same chunks and hashes.
"""

from __future__ import annotations

import hashlib

from lexflow.extraction import Section
from lexflow.services.extraction_queue import ChunkData

# Break points in order of preference, and how much of each to keep in the
# chunk that ends there.
_BREAKS = (("\n\n", 0), ("\n", 0), (". ", 1), ("? ", 1), ("! ", 1), (" ", 0))


def _end(text: str, start: int, size: int) -> int:
    limit = start + size
    if limit >= len(text):
        return len(text)
    floor = start + size // 2  # never make a chunk shorter than half the size
    for separator, keep in _BREAKS:
        found = text.rfind(separator, floor, limit)
        if found != -1:
            return found + keep
    return limit  # one very long word: cut it


def _next_start(text: str, start: int, end: int, overlap: int) -> int:
    candidate = max(end - overlap, start + 1)
    # Begin the overlap at the start of a word.
    while candidate < end and not text[candidate - 1].isspace():
        candidate += 1
    return candidate


def chunk_sections(sections: list[Section], size: int, overlap: int) -> list[ChunkData]:
    chunks: list[ChunkData] = []
    for section_number, section in enumerate(sections, start=1):
        text = section.text
        start = 0
        while start < len(text):
            while start < len(text) and text[start].isspace():
                start += 1
            if start >= len(text):
                break
            end = _end(text, start, size)
            stop = end
            while stop > start and text[stop - 1].isspace():
                stop -= 1
            piece = text[start:stop]
            chunks.append(
                ChunkData(
                    number=len(chunks) + 1,
                    section_number=section_number,
                    page_number=section.page_number,
                    char_start=start,
                    char_end=stop,
                    text=piece,
                    content_sha256=hashlib.sha256(piece.encode("utf-8")).hexdigest(),
                )
            )
            if end >= len(text):
                break
            start = _next_start(text, start, end, overlap)
    return chunks
