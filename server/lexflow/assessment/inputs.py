"""What an outcome assessment may use, and the evidence gate (D7-3).

Only findings a lawyer **accepted** (``accepted`` or ``edited``) in one ready
analysis run are used; an edited finding is used in the lawyer's wording.
Unreviewed and rejected findings, reviewers' notes, review history, the case
description and the timeline are never read here, so they can never reach a
provider.

Precedents are the accepted precedent comparisons (``P1``…) of the run. Each
is used with the judgment passage it was compared against, reloaded from the
collection and checked against the content hash recorded with the run: a
passage that changed or disappeared is left out (and counted), never replaced.

An assessment needs at least one accepted fact, issue or contradiction and at
least one accepted precedent with an unchanged passage; otherwise the gate
reports why, and no provider is called.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from lexflow.models import AnalysisRun, Judgment, JudgmentChunk, JudgmentSource
from lexflow.services import reviews

ACCEPTED = frozenset({"accepted", "edited"})

GATE_REASONS: dict[str, str] = {
    "no-accepted-findings": (
        "No fact, issue or contradiction of this analysis has been accepted by a lawyer yet. "
        "An assessment uses accepted findings only."
    ),
    "no-accepted-precedents": (
        "No precedent comparison of this analysis has been accepted by a lawyer. An assessment "
        "is never made without a supporting precedent."
    ),
    "precedent-passages-changed": (
        "The judgment passages behind the accepted precedent comparisons changed or were removed "
        "after the analysis, so they cannot support an assessment."
    ),
}


@dataclass(frozen=True)
class InputFinding:
    """An accepted fact (F), issue (I) or contradiction (C)."""

    kind: str
    id: str
    text: str  # the lawyer's wording when edited, otherwise the validated AI wording
    edited: bool
    review_version: int


@dataclass(frozen=True)
class InputPrecedent:
    """An accepted precedent comparison (P) with its judgment passage."""

    id: str
    summary: str  # the lawyer's wording when edited, otherwise the validated AI wording
    edited: bool
    review_version: int
    judgment_id: uuid.UUID
    title: str
    court: str
    citation: str | None
    year: int | None
    synthetic: bool
    chunk_id: uuid.UUID
    section_number: int
    page_number: int | None
    text: str
    content_sha256: str


@dataclass
class Inputs:
    findings: list[InputFinding] = field(default_factory=list)
    precedents: list[InputPrecedent] = field(default_factory=list)
    # Findings not used, by reason: "unreviewed", "rejected", "passage-changed".
    excluded: dict[str, int] = field(default_factory=dict)

    def finding_ids(self) -> set[str]:
        return {f.id for f in self.findings} | {p.id for p in self.precedents}

    def precedent(self, ref: str) -> InputPrecedent | None:
        return next((p for p in self.precedents if p.id == ref), None)

    @property
    def all_synthetic(self) -> bool:
        return bool(self.precedents) and all(p.synthetic for p in self.precedents)

    def record(self) -> dict[str, Any]:
        """What is stored with the assessment: references, versions and hashes, never text."""
        return {
            "findings": [
                {"id": f.id, "kind": f.kind, "reviewVersion": f.review_version, "edited": f.edited}
                for f in self.findings
            ],
            "precedents": [
                {
                    "id": p.id,
                    "reviewVersion": p.review_version,
                    "edited": p.edited,
                    "judgmentId": str(p.judgment_id),
                    "chunkId": str(p.chunk_id),
                    "contentSha256": p.content_sha256,
                    "synthetic": p.synthetic,
                }
                for p in self.precedents
            ],
            "excluded": dict(sorted(self.excluded.items())),
        }

    def gate(self) -> str | None:
        """The reason code when there is no basis for an assessment, else None."""
        if not self.findings:
            return "no-accepted-findings"
        if not self.precedents:
            if self.excluded.get("passage-changed"):
                return "precedent-passages-changed"
            return "no-accepted-precedents"
        return None


def _count(excluded: dict[str, int], reason: str) -> None:
    excluded[reason] = excluded.get(reason, 0) + 1


def gather(session: Session, run: AnalysisRun) -> Inputs:
    """The accepted findings of a ready run and the passages of its accepted precedents."""
    decided = reviews.current(session, run.id)
    items = (run.evidence or {}).get("items") or {}
    inputs = Inputs()
    wanted: list[tuple[reviews.Finding, Any]] = []
    for item in reviews.findings(run.result):
        review = decided.get(item.id)
        status = review.status if review is not None else "unreviewed"
        if status not in ACCEPTED or review is None:
            _count(inputs.excluded, "rejected" if status == "rejected" else "unreviewed")
            continue
        text = (review.reviewed_text if review.status == "edited" else item.text) or ""
        if item.kind != "precedent":
            inputs.findings.append(
                InputFinding(item.kind, item.id, text, review.status == "edited", review.version)
            )
        else:
            wanted.append((item, review))

    chunk_ids: list[uuid.UUID] = []
    for item, _ in wanted:
        try:
            chunk_ids.append(uuid.UUID(str((item.item.get("passage") or {}).get("chunkId"))))
        except ValueError:
            continue
    rows = (
        session.execute(
            select(JudgmentChunk, Judgment, JudgmentSource)
            .join(Judgment, Judgment.id == JudgmentChunk.judgment_id)
            .join(JudgmentSource, JudgmentSource.id == Judgment.source_id)
            .where(JudgmentChunk.id.in_(chunk_ids))
        )
        .tuples()
        .all()
        if chunk_ids
        else []
    )
    found = {chunk.id: (chunk, judgment, source) for chunk, judgment, source in rows}
    for item, review in wanted:
        stored = item.item
        passage = stored.get("passage") or {}
        recorded = items.get(str(stored.get("evidenceId"))) if isinstance(items, dict) else None
        try:
            chunk_id = uuid.UUID(str(passage.get("chunkId")))
        except ValueError:
            _count(inputs.excluded, "passage-changed")
            continue
        hit = found.get(chunk_id)
        expected = recorded.get("contentSha256") if isinstance(recorded, dict) else None
        if hit is None or expected is None:
            _count(inputs.excluded, "passage-changed")
            continue
        chunk, judgment, source = hit
        # The same comparison as the analysis tab's "changed since" flag (Phase 6).
        if chunk.content_sha256 != expected:
            _count(inputs.excluded, "passage-changed")
            continue
        inputs.precedents.append(
            InputPrecedent(
                id=item.id,
                summary=(review.reviewed_text if review.status == "edited" else item.text) or "",
                edited=review.status == "edited",
                review_version=review.version,
                judgment_id=judgment.id,
                title=judgment.title,
                court=judgment.court,
                citation=judgment.citation,
                year=judgment.year,
                # Synthetic if the collection says so now or said so at the run.
                synthetic=bool(source.is_synthetic or stored.get("synthetic")),
                chunk_id=chunk.id,
                section_number=chunk.section_number,
                page_number=chunk.page_number,
                text=chunk.text,
                content_sha256=expected,
            )
        )
    return inputs
