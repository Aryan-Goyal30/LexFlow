"""The evidence one analysis run may use, each passage with an opaque id.

- ``D1``, ``D2``, ... are passages (chunks) of the case's selected documents:
  only documents that are not deleted and whose text is ready. Each
  document's first passage is always included (while the limits allow), then
  the passages that share the most words with the case's title and summary.
- ``J1``, ``J2``, ... are judgment passages found by keyword search of the
  judgment collection with the case's most frequent words. When the
  collection is empty (or has nothing matching), there are none, and the
  result says no precedents were available (owner decision D5).

Everything is deterministic for the same data and settings: ties are broken
by document order and passage number. Limits: documents, passages, judgment
passages and total characters (case context + passages). The model only ever
sees these ids; the server maps them back to documents, pages and judgments.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import date

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from lexflow.models import (
    Case,
    Document,
    DocumentChunk,
    DocumentExtraction,
    Judgment,
    JudgmentChunk,
    JudgmentSource,
    TimelineEvent,
)
from lexflow.services import judgments as judgment_search

TIMELINE_MAX = 30
DESCRIPTION_MAX = 3_000
EVENT_TEXT_MAX = 300
QUERY_TERMS = 8

_WORD = re.compile(r"[a-z][a-z0-9]{2,}")
# Common English and legal-procedure words that say nothing about a case.
_STOP = frozenset(
    """
    the and for with that this from was were are has have had not but its into upon such
    any all may shall will would could should said under which who whom whose what when
    where there their they them than then been being also only other same each per out
    our your his her him she one two three made make between about after before over
    case cases matter court petitioner respondent plaintiff defendant party parties
    """.split()  # noqa: SIM905 - a word list reads better as text
)


@dataclass(frozen=True)
class Passage:
    """A case-document passage (``D``)."""

    id: str
    document_id: uuid.UUID
    document_name: str
    chunk_id: uuid.UUID
    chunk_number: int
    section_number: int
    page_number: int | None
    text: str
    content_sha256: str


@dataclass(frozen=True)
class JudgmentPassage:
    """A judgment passage (``J``) and the judgment's metadata."""

    id: str
    judgment_id: uuid.UUID
    title: str
    court: str
    citation: str | None
    year: int | None
    synthetic: bool
    rank: int
    chunk_id: uuid.UUID
    section_number: int
    page_number: int | None
    text: str
    content_sha256: str


@dataclass(frozen=True)
class TimelineItem:
    date: date
    label: str
    description: str


@dataclass(frozen=True)
class CaseContext:
    """Background for the model; it cannot be cited as a source."""

    case_number: str
    title: str
    practice_area: str
    status: str
    court_name: str | None
    opposing_party: str | None
    description: str
    timeline: list[TimelineItem]


@dataclass
class Evidence:
    context: CaseContext
    passages: list[Passage] = field(default_factory=list)
    judgments: list[JudgmentPassage] = field(default_factory=list)
    documents_selected: int = 0
    documents_without_text: list[uuid.UUID] = field(default_factory=list)
    characters: int = 0
    truncated: bool = False

    @property
    def documents_used(self) -> int:
        return len({p.document_id for p in self.passages})

    def passage(self, evidence_id: str) -> Passage | None:
        return next((p for p in self.passages if p.id == evidence_id), None)

    def judgment(self, evidence_id: str) -> JudgmentPassage | None:
        return next((j for j in self.judgments if j.id == evidence_id), None)

    def record(self) -> dict[str, object]:
        """What is stored with the run: references and hashes, never the text."""
        return {
            "documentsSelected": self.documents_selected,
            "documentsWithoutText": [str(d) for d in self.documents_without_text],
            "characters": self.characters,
            "truncated": self.truncated,
            "items": {
                **{
                    p.id: {
                        "kind": "document",
                        "documentId": str(p.document_id),
                        "chunkId": str(p.chunk_id),
                        "chunkNumber": p.chunk_number,
                        "sectionNumber": p.section_number,
                        "pageNumber": p.page_number,
                        "contentSha256": p.content_sha256,
                    }
                    for p in self.passages
                },
                **{
                    j.id: {
                        "kind": "judgment",
                        "judgmentId": str(j.judgment_id),
                        "chunkId": str(j.chunk_id),
                        "sectionNumber": j.section_number,
                        "pageNumber": j.page_number,
                        "rank": j.rank,
                        "contentSha256": j.content_sha256,
                    }
                    for j in self.judgments
                },
            },
        }


@dataclass(frozen=True)
class Limits:
    max_documents: int
    max_passages: int
    max_precedents: int
    max_chars: int
    # Which judgments the analysis may compare the case with (None: all). While
    # the outcome-assessment demo is on, synthetic ones only: the assessment
    # never uses a genuine judgment (genuine-precedents gate), so a demo
    # analysis built on genuine judgments could never be assessed.
    judgment_origin: judgment_search.Origin | None = None
    # (judgment title prefix, words): passages that must be included, for the
    # prepared demonstration provider (``lexflow/analysis/prepared.py``).
    pinned: tuple[tuple[str, str], ...] = ()


def terms(text_: str) -> list[str]:
    return [w for w in _WORD.findall(text_.lower()) if w not in _STOP]


def _context(session: Session, case: Case) -> CaseContext:
    events = session.scalars(
        select(TimelineEvent)
        .where(TimelineEvent.case_id == case.id)
        .order_by(TimelineEvent.event_date.desc(), TimelineEvent.created_at.desc())
        .limit(TIMELINE_MAX)
    ).all()
    return CaseContext(
        case_number=case.case_number,
        title=case.title,
        practice_area=case.practice_area,
        status=case.status,
        court_name=case.court_name,
        opposing_party=case.opposing_party,
        description=case.description[:DESCRIPTION_MAX],
        timeline=[
            TimelineItem(e.event_date, e.label[:EVENT_TEXT_MAX], e.description[:EVENT_TEXT_MAX])
            for e in reversed(events)
        ],
    )


def context_chars(context: CaseContext) -> int:
    return (
        len(context.title)
        + len(context.description)
        + sum(len(e.label) + len(e.description) for e in context.timeline)
    )


def eligible_documents(
    session: Session, case_id: uuid.UUID, document_ids: list[uuid.UUID]
) -> tuple[list[Document], list[uuid.UUID]]:
    """The selected documents of this case that can be analysed (live, text
    ready), by upload date then name; and the selected ones that cannot."""
    rows = session.execute(
        select(Document, DocumentExtraction.status)
        .outerjoin(DocumentExtraction, DocumentExtraction.document_id == Document.id)
        .where(
            Document.case_id == case_id,
            Document.id.in_(document_ids),
            Document.deleted_at.is_(None),
        )
        .order_by(Document.uploaded_on, func.lower(Document.name), Document.id)
    ).all()
    ready = [d for d, status in rows if status == "ready"]
    ready_ids = {d.id for d in ready}
    return ready, [d for d in document_ids if d not in ready_ids]


def _judgment_query(context: CaseContext) -> str:
    counts = Counter(terms(f"{context.title} {context.title} {context.description}"))
    top = [w for w, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:QUERY_TERMS]]
    return " or ".join(top)


def _judgments(
    session: Session,
    context: CaseContext,
    limit: int,
    origin: judgment_search.Origin | None = None,
) -> list[JudgmentPassage]:
    if limit == 0 or session.scalar(text("SELECT to_regclass('judgments')")) is None:
        return []
    query = _judgment_query(context)
    if not query:
        return []
    ranked = judgment_search.keyword(session, query, judgment_search.Filters(origin=origin), limit)
    if not ranked:
        return []
    meta = {
        j.id: (j, s)
        for j, s in session.execute(
            select(Judgment, JudgmentSource)
            .join(JudgmentSource, JudgmentSource.id == Judgment.source_id)
            .where(Judgment.id.in_([r.judgment_id for r in ranked]))
        ).all()
    }
    found: list[JudgmentPassage] = []
    for rank, hit in enumerate(ranked, start=1):
        judgment, source = meta[hit.judgment_id]
        found.append(
            JudgmentPassage(
                id=f"J{rank}",
                judgment_id=judgment.id,
                title=judgment.title,
                court=judgment.court,
                citation=judgment.citation,
                year=judgment.year,
                synthetic=source.is_synthetic,
                rank=rank,
                chunk_id=hit.passage.chunk_id,
                section_number=hit.passage.section_number,
                page_number=hit.passage.page_number,
                text=hit.passage.text,
                content_sha256=hashlib.sha256(hit.passage.text.encode()).hexdigest(),
            )
        )
    return found


def _with_pinned(
    session: Session, found: list[JudgmentPassage], limits: Limits
) -> list[JudgmentPassage]:
    """``found`` plus the chunks holding each pinned passage (by judgment title and words)."""
    if not limits.pinned or session.scalar(text("SELECT to_regclass('judgments')")) is None:
        return found
    have = {p.chunk_id for p in found}
    pinned: list[JudgmentPassage] = []
    for title, words in limits.pinned:
        want = " ".join(words.split()).casefold()
        rows = session.execute(
            select(Judgment, JudgmentSource, JudgmentChunk)
            .join(JudgmentSource, JudgmentSource.id == Judgment.source_id)
            .join(JudgmentChunk, JudgmentChunk.judgment_id == Judgment.id)
            .where(Judgment.title.ilike(f"{title}%"))
            .order_by(JudgmentChunk.number)
        ).all()
        for judgment, source, chunk in rows:
            if chunk.id in have or want not in " ".join(chunk.text.split()).casefold():
                continue
            if limits.judgment_origin == "synthetic" and not source.is_synthetic:
                continue
            have.add(chunk.id)
            pinned.append(
                JudgmentPassage(
                    id="",
                    judgment_id=judgment.id,
                    title=judgment.title,
                    court=judgment.court,
                    citation=judgment.citation,
                    year=judgment.year,
                    synthetic=source.is_synthetic,
                    rank=0,
                    chunk_id=chunk.id,
                    section_number=chunk.section_number,
                    page_number=chunk.page_number,
                    text=chunk.text,
                    content_sha256=hashlib.sha256(chunk.text.encode()).hexdigest(),
                )
            )
            break
    merged = [*pinned, *found]
    return [replace(p, id=f"J{i}", rank=i) for i, p in enumerate(merged, start=1)]


def assemble(
    session: Session, case: Case, document_ids: list[uuid.UUID], limits: Limits
) -> Evidence:
    context = _context(session, case)
    documents, without_text = eligible_documents(session, case.id, document_ids)
    documents = documents[: limits.max_documents]
    evidence = Evidence(
        context=context,
        documents_selected=len(document_ids),
        documents_without_text=without_text,
    )
    budget = limits.max_chars - context_chars(context)

    # Judgment passages first take at most a quarter of the budget.
    judgments = _judgments(session, context, limits.max_precedents, limits.judgment_origin)
    judgments = _with_pinned(session, judgments, limits)
    judgment_budget = budget // 4
    for passage in judgments:
        if len(passage.text) > judgment_budget:
            evidence.truncated = True
            break
        judgment_budget -= len(passage.text)
        budget -= len(passage.text)
        evidence.judgments.append(passage)

    if not documents:
        evidence.characters = limits.max_chars - budget
        return evidence
    order = {d.id: i for i, d in enumerate(documents)}
    names = {d.id: d.name for d in documents}
    chunks = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id.in_(list(order)))
        .order_by(DocumentChunk.document_id, DocumentChunk.number)
    ).all()
    wanted = Counter(terms(f"{context.title} {context.description}"))

    def score(chunk: DocumentChunk) -> int:
        return sum(min(n, 3) for w, n in Counter(terms(chunk.text)).items() if w in wanted)

    first_of: dict[uuid.UUID, DocumentChunk] = {}
    for chunk in chunks:  # ordered by number within each document
        first_of.setdefault(chunk.document_id, chunk)
    firsts = sorted(first_of.values(), key=lambda c: order[c.document_id])
    first_ids = {c.id for c in firsts}
    rest = sorted(
        (c for c in chunks if c.id not in first_ids),
        key=lambda c: (-score(c), order[c.document_id], c.number),
    )
    chosen: list[DocumentChunk] = []
    for chunk in [*firsts, *rest]:
        if len(chosen) == limits.max_passages or len(chunk.text) > budget:
            evidence.truncated = True
            continue
        budget -= len(chunk.text)
        chosen.append(chunk)
    chosen.sort(key=lambda c: (order[c.document_id], c.number))
    evidence.passages = [
        Passage(
            id=f"D{i}",
            document_id=c.document_id,
            document_name=names[c.document_id],
            chunk_id=c.id,
            chunk_number=c.number,
            section_number=c.section_number,
            page_number=c.page_number,
            text=c.text,
            content_sha256=c.content_sha256,
        )
        for i, c in enumerate(chosen, start=1)
    ]
    evidence.characters = limits.max_chars - budget
    return evidence
