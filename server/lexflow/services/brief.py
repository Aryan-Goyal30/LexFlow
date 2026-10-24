"""The case brief (Phase 6): a Word document of the findings a lawyer accepted.

Built on request from one ready analysis run and its review decisions, with
python-docx, on this computer. No model is called and nothing is stored.

What it contains, and what it never contains:

- **only accepted findings** (status ``accepted`` or ``edited``); an edited
  finding appears in the lawyer's wording, marked as such. Unreviewed and
  rejected findings are left out; the brief says how many there are;
- each finding with its citation as validated and stored with the run:
  document name, page or part, and the verified quote; for a precedent, the
  judgment's title, court, citation and year from the collection;
  synthetic judgments are labelled as fictional, and sources that changed
  after the run are flagged (never replaced);
- who accepted each finding and when, and the decision-support disclaimer;
- never a reviewer's note, internal ids, or the word "approved" for the
  brief as a whole.
"""

from __future__ import annotations

import io
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import docx
from docx.document import Document as DocumentObject

from lexflow.models import AnalysisFindingReview, AnalysisRun, Case, User
from lexflow.services.reviews import KIND_LABEL, Finding, findings

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
DISCLAIMER = (
    "AI output in LexFlow is decision support for the advocate. It is not legal advice and "
    "does not replace a lawyer's judgment or a court's decision. LexFlow checks that each quote "
    "occurs in the source it cites; it does not check that the reading of it is legally right. "
    "This brief contains only findings a lawyer accepted; verify every point against its source."
)
SYNTHETIC_LABEL = "SYNTHETIC test judgment: fictional, not real case law."
PASSAGE_CHANGED_NOTE = (
    "This judgment passage changed after the analysis (the judgment was re-imported or removed). "
    "The comparison is shown as it was made at the time."
)
CHANGED_NOTE = (
    "This source changed after the analysis (the document was re-extracted or deleted, or the "
    "judgment removed). The quote is shown as it was verified at the time."
)
ACCEPTED = frozenset({"accepted", "edited"})
_SECTIONS = (
    ("fact", "Facts"),
    ("issue", "Legal issues"),
    ("precedent", "Precedent comparisons"),
    ("contradiction", "Contradictions"),
)
_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def filename(case: Case, day: str) -> str:
    stem = _UNSAFE_NAME.sub("-", f"case-brief-{case.case_number}-{day}").strip("-.")
    return f"{stem or 'case-brief'}.docx"


@dataclass(frozen=True)
class Counts:
    accepted: int
    edited: int
    rejected: int
    unreviewed: int

    @property
    def included(self) -> int:
        return self.accepted + self.edited


def counts(items: list[Finding], reviews: Mapping[str, AnalysisFindingReview]) -> Counts:
    statuses = [reviews[f.id].status if f.id in reviews else "unreviewed" for f in items]
    return Counts(
        accepted=statuses.count("accepted"),
        edited=statuses.count("edited"),
        rejected=statuses.count("rejected"),
        unreviewed=statuses.count("unreviewed"),
    )


def _where(source: Mapping[str, Any]) -> str:
    page = source.get("pageNumber")
    place = f"page {page}" if page else f"part {source.get('sectionNumber')}"
    return f"{source.get('documentName', 'a document')}, {place}"


class _Writer:
    def __init__(
        self, doc: DocumentObject, zone: ZoneInfo, people: Mapping[uuid.UUID, User]
    ) -> None:
        self.doc = doc
        self.zone = zone
        self.people = people

    def day(self, moment: datetime) -> str:
        return moment.astimezone(self.zone).strftime("%d %B %Y").lstrip("0")

    def line(self, text: str, *, style: str | None = None, italic: bool = False) -> None:
        paragraph = self.doc.add_paragraph(style=style)
        run = paragraph.add_run(text)
        run.italic = italic

    def labelled(self, label: str, text: str) -> None:
        paragraph = self.doc.add_paragraph()
        paragraph.add_run(f"{label}: ").bold = True
        paragraph.add_run(text)

    def sources(self, sources: list[Mapping[str, Any]], changed: set[str]) -> None:
        for source in sources:
            self.line(f"Source: {_where(source)}: “{source.get('quote', '')}”", style="List Bullet")
            if source.get("evidenceId") in changed:
                self.line(CHANGED_NOTE, style="List Bullet 2", italic=True)

    def decision(self, review: AnalysisFindingReview) -> None:
        who = self.people.get(review.reviewed_by_id) if review.reviewed_by_id else None
        verb = "Accepted with the lawyer's wording" if review.status == "edited" else "Accepted"
        by = f" by {who.name}" if who is not None else ""
        self.line(f"{verb}{by} on {self.day(review.reviewed_at)}.", italic=True)


def build(
    *,
    case: Case,
    run: AnalysisRun,
    reviews: Mapping[str, AnalysisFindingReview],
    people: Mapping[uuid.UUID, User],
    changed: set[str],
    prepared_by: User,
    now: datetime,
    zone: str,
) -> bytes:
    """The brief as DOCX bytes. The caller checks access and that at least one
    finding is accepted."""
    tz = ZoneInfo(zone)
    items = findings(run.result)
    tally = counts(items, reviews)
    doc = docx.Document()
    props = doc.core_properties
    props.title = f"Case brief: {case.case_number}"
    props.author = "LexFlow"
    props.last_modified_by = "LexFlow"
    props.comments = ""
    props.created = props.modified = now.replace(tzinfo=None)
    w = _Writer(doc, tz, people)

    doc.add_heading(f"Case brief: {case.title}", level=0)
    w.labelled("Case number", case.case_number)
    for label, value in (
        ("Court", case.court_name),
        ("Practice area", case.practice_area),
        ("Status", case.status),
        ("Opposing party", case.opposing_party),
    ):
        if value:
            w.labelled(label, value)
    pipeline = (run.evidence or {}).get("pipeline") or {}
    versions = f"prompt {run.prompt_version}"
    if pipeline.get("validatorVersion"):
        versions += f", validation {pipeline['validatorVersion']}"
    w.labelled(
        "Prepared",
        f"{w.day(now)} by {prepared_by.name}, from the AI analysis of {w.day(run.created_at)} "
        f"(provider {run.provider}, model {run.model}; {versions}).",
    )
    if run.provider == "scripted":
        w.line(
            "Produced by the scripted test provider: not AI, for checking LexFlow only.",
            italic=True,
        )

    doc.add_heading("Review status", level=1)
    w.line(
        f"This brief contains only the {tally.included} "
        f"{'finding' if tally.included == 1 else 'findings'} a lawyer accepted "
        f"({tally.edited} in the lawyer's own wording). Not included: {tally.unreviewed} "
        f"unreviewed and {tally.rejected} rejected."
    )
    if tally.unreviewed:
        w.line(
            f"Review is not complete: {tally.unreviewed} "
            f"{'finding has' if tally.unreviewed == 1 else 'findings have'} not been reviewed "
            "and are not in this brief.",
            italic=True,
        )

    accepted = {f.id for f in items if f.id in reviews and reviews[f.id].status in ACCEPTED}
    for kind, heading in _SECTIONS:
        chosen = [f for f in items if f.kind == kind and f.id in accepted]
        if not chosen:
            continue
        doc.add_heading(heading, level=1)
        for finding in chosen:
            review = reviews[finding.id]
            text = review.reviewed_text if review.status == "edited" else finding.text
            doc.add_heading(f"{KIND_LABEL[kind]} {finding.id}", level=2)
            w.line(text or "")
            if review.status == "edited":
                w.line("Wording by the reviewing lawyer.", italic=True)
            _details(w, finding, accepted, changed)
            w.decision(review)

    doc.add_heading("About this brief", level=1)
    w.line(DISCLAIMER)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def _details(w: _Writer, finding: Finding, accepted: set[str], changed: set[str]) -> None:
    item = finding.item
    if finding.kind == "fact":
        w.sources([item.get("source") or {}], changed)
    elif finding.kind == "issue":
        refs = [
            ref if ref in accepted else f"{ref} (not in this brief)"
            for ref in item.get("factIds") or []
        ]
        w.line(f"Rests on: {', '.join(refs) or 'no fact'}.")
    elif finding.kind == "precedent":
        meta = ", ".join(
            str(x) for x in (item.get("court"), item.get("citation"), item.get("year")) if x
        )
        w.labelled("Judgment", f"{item.get('title', '')}{f' ({meta})' if meta else ''}")
        if item.get("synthetic"):
            w.line(SYNTHETIC_LABEL, italic=True)
        passage = item.get("passage") or {}
        page = passage.get("pageNumber")
        place = f"page {page}" if page else f"part {passage.get('sectionNumber')}"
        w.line(f"Compared passage: {place} of the judgment.")
        if item.get("evidenceId") in changed:
            w.line(PASSAGE_CHANGED_NOTE, italic=True)
        for label, key in (("Similarity", "similarities"), ("Difference", "differences")):
            for point in item.get(key) or []:
                w.line(f"{label} (as stated by the AI): {point}", style="List Bullet")
    elif finding.kind == "contradiction":
        w.sources(list(item.get("sources") or []), changed)
