"""Checks every item of a model's answer against the run's evidence.

What survives, and only that, is stored and shown:

- a **fact** cites exactly one case passage (``D`` id) that was sent in this
  run, and its quote occurs in that passage (after Unicode and whitespace
  normalisation, at least ``QUOTE_MIN`` characters); otherwise it is removed;
- a **precedent** cites a judgment passage (``J`` id) retrieved for this run;
  one citing any other judgment is rejected (the brief: "an output citing an
  unknown judgment is rejected"). Its title, court and citation come from the
  collection, never from the model;
- a **contradiction** needs at least two distinct verified sources;
- an **issue** keeps only references to surviving facts and is removed when
  none are left;
- any item whose wording names a law-report citation that occurs nowhere in
  the evidence is removed (an invented citation cannot hide in prose);
- an outcome assessment is never shown (Phase 7) and is counted if returned.

Each removal is counted with its reason. When nothing verifiable is left, the
result says the evidence is insufficient instead of guessing.

This establishes provenance, not correctness: a statement that is supported
by a verified quote can still be a wrong reading of it. The lawyer decides.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from lexflow.analysis.evidence import Evidence, Passage
from lexflow.analysis.output import EVIDENCE_ID, ParsedOutput
from lexflow.schemas import (
    AnalysisContradictionOut,
    AnalysisFactOut,
    AnalysisIssueOut,
    AnalysisPassageRefOut,
    AnalysisPrecedentOut,
    AnalysisRemovedOut,
    AnalysisRemovedReasonOut,
    AnalysisResultOut,
    AnalysisSourceOut,
)

QUOTE_MIN = 15

REASONS: dict[str, str] = {
    "unknown-evidence": "Cited a passage that was not part of this analysis's evidence.",
    "quote-not-found": "Its quote does not occur in the passage it cites.",
    "quote-too-short": f"Its quote was shorter than {QUOTE_MIN} characters, too short to verify.",
    "unknown-judgment": "Cited a judgment that was not retrieved for this analysis.",
    "unverified-citation": "Named a citation that does not appear in the evidence.",
    "issue-without-facts": "Did not rest on any verified fact.",
    "contradiction-unsupported": "Had fewer than two verified sources.",
    "duplicate": "Repeated an item already given.",
    "malformed": "Did not have the expected shape.",
    "over-limit": "Went beyond the number of items allowed.",
    "outcome-discarded": "An outcome assessment was returned; LexFlow does not show one.",
}

NO_PASSAGES = "None of the selected documents had text that could be analysed."
MODEL_INSUFFICIENT = "The model reported that the evidence is not enough for a useful analysis."
NOTHING_VERIFIED = "Nothing in the answer could be verified against the evidence."

# Typographic quotes and dashes, no-break space and soft hyphen (by code point,
# so the source stays plain ASCII).
_TYPOGRAPHY = str.maketrans(
    {
        0x2018: "'",
        0x2019: "'",
        0x201C: '"',
        0x201D: '"',
        0x2013: "-",
        0x2014: "-",
        0x00A0: " ",
        0x00AD: None,
    }
)
_SPACE = re.compile(r"\s+")

# Law-report citations as written in Indian practice: "AIR 1973 SC 1461",
# "(2017) 10 SCC 1", "1997 (6) SCC 241", "[1950] SCR 88", "2019 SCC OnLine Del 123".
_CITATION = re.compile(
    r"\bAIR\s+\d{4}\s+[A-Z][A-Za-z.]*\s*\d+"
    r"|[(\[]\d{4}[)\]]\s*\d*\s*(?:SCC|SCR|SCALE|SCJ|ILR|MLJ|KLT|Cri\s?LJ|All\s?ER)\b(?:\s*\w+)?\s*\d+"
    r"|\b\d{4}\s*\(\d+\)\s*(?:SCC|SCR|SCALE)\s*\d+"
    r"|\b\d{4}\s+SCC\s+OnLine\s+\w+\s+\d+"
)


def normalise(text: str) -> str:
    return _SPACE.sub(" ", unicodedata.normalize("NFKC", text).translate(_TYPOGRAPHY)).strip()


class _Tally:
    def __init__(self) -> None:
        self.counts: Counter[str] = Counter()

    def remove(self, code: str, count: int = 1) -> None:
        if count:
            self.counts[code] += count

    def result(self) -> AnalysisRemovedOut:
        return AnalysisRemovedOut(
            count=sum(self.counts.values()),
            reasons=[
                AnalysisRemovedReasonOut(code=code, message=REASONS[code], count=n)
                for code, n in sorted(self.counts.items())
            ],
        )


class _Checker:
    def __init__(self, evidence: Evidence) -> None:
        self.evidence = evidence
        self._normal = {p.id: normalise(p.text) for p in evidence.passages}
        known = [normalise(p.text) for p in evidence.passages]
        known += [normalise(j.text) for j in evidence.judgments]
        known += [normalise(j.citation) for j in evidence.judgments if j.citation]
        self._known_text = "\n".join(known)

    def source(self, evidence_id: str, quote: str) -> AnalysisSourceOut | str:
        """A verified source, or the reason code it fails."""
        passage: Passage | None = (
            self.evidence.passage(evidence_id) if EVIDENCE_ID.fullmatch(evidence_id) else None
        )
        if passage is None:
            return "unknown-evidence"
        wanted = normalise(quote)
        if len(wanted) < QUOTE_MIN:
            return "quote-too-short"
        if wanted not in self._normal[passage.id]:
            return "quote-not-found"
        return AnalysisSourceOut(
            evidence_id=passage.id,
            document_id=passage.document_id,
            document_name=passage.document_name,
            chunk_id=passage.chunk_id,
            section_number=passage.section_number,
            page_number=passage.page_number,
            quote=wanted,
        )

    def invented_citation(self, *texts: str) -> bool:
        for text in texts:
            for match in _CITATION.finditer(normalise(text)):
                if match.group(0) not in self._known_text:
                    return True
        return False


def validate(parsed: ParsedOutput, evidence: Evidence) -> AnalysisResultOut:
    tally = _Tally()
    check = _Checker(evidence)
    tally.remove("malformed", parsed.malformed)
    tally.remove("over-limit", parsed.over_limit)
    if parsed.outcome_discarded:
        tally.remove("outcome-discarded")

    facts: list[AnalysisFactOut] = []
    seen_fact_ids: set[str] = set()
    for fact in parsed.facts:
        if fact.id in seen_fact_ids:
            tally.remove("duplicate")
            continue
        source = check.source(fact.evidence, fact.quote)
        if isinstance(source, str):
            tally.remove(source)
            continue
        if check.invented_citation(fact.statement):
            tally.remove("unverified-citation")
            continue
        seen_fact_ids.add(fact.id)
        facts.append(AnalysisFactOut(id=fact.id, statement=fact.statement, source=source))

    kept_ids = {f.id for f in facts}
    issues: list[AnalysisIssueOut] = []
    for issue in parsed.issues:
        refs = list(dict.fromkeys(i for i in issue.fact_ids if i in kept_ids))
        if not refs:
            tally.remove("issue-without-facts")
            continue
        if check.invented_citation(issue.question):
            tally.remove("unverified-citation")
            continue
        issues.append(
            AnalysisIssueOut(id=f"I{len(issues) + 1}", question=issue.question, fact_ids=refs)
        )

    precedents: list[AnalysisPrecedentOut] = []
    seen_judgments: set[str] = set()
    for item in parsed.precedents:
        passage = evidence.judgment(item.evidence) if EVIDENCE_ID.fullmatch(item.evidence) else None
        if passage is None:
            tally.remove("unknown-judgment")
            continue
        if passage.id in seen_judgments:
            tally.remove("duplicate")
            continue
        if check.invented_citation(item.summary, *item.similarities, *item.differences):
            tally.remove("unverified-citation")
            continue
        seen_judgments.add(passage.id)
        precedents.append(
            AnalysisPrecedentOut(
                id=f"P{len(precedents) + 1}",
                evidence_id=passage.id,
                judgment_id=passage.judgment_id,
                title=passage.title,
                court=passage.court,
                citation=passage.citation,
                year=passage.year,
                synthetic=passage.synthetic,
                retrieval_rank=passage.rank,
                passage=AnalysisPassageRefOut(
                    chunk_id=passage.chunk_id,
                    section_number=passage.section_number,
                    page_number=passage.page_number,
                ),
                summary=item.summary,
                similarities=[s.strip() for s in item.similarities if s.strip()],
                differences=[d.strip() for d in item.differences if d.strip()],
            )
        )

    contradictions: list[AnalysisContradictionOut] = []
    for contradiction in parsed.contradictions:
        sources: list[AnalysisSourceOut] = []
        for raw in contradiction.sources:
            source = check.source(raw.evidence, raw.quote)
            if isinstance(source, AnalysisSourceOut) and all(
                (s.evidence_id, s.quote) != (source.evidence_id, source.quote) for s in sources
            ):
                sources.append(source)
        if len(sources) < 2:
            tally.remove("contradiction-unsupported")
            continue
        if check.invented_citation(contradiction.description):
            tally.remove("unverified-citation")
            continue
        contradictions.append(
            AnalysisContradictionOut(
                id=f"C{len(contradictions) + 1}",
                description=contradiction.description,
                sources=sources,
            )
        )

    reason: str | None = None
    if not evidence.passages:
        reason = NO_PASSAGES
    elif parsed.insufficient_evidence:
        reason = MODEL_INSUFFICIENT
    elif not facts and not precedents and not contradictions:
        reason = NOTHING_VERIFIED
    return AnalysisResultOut(
        facts=facts,
        issues=issues,
        precedents=precedents,
        contradictions=contradictions,
        insufficient_evidence=reason is not None,
        insufficient_reason=reason,
        precedents_available=bool(evidence.judgments),
        removed=tally.result(),
    )


def insufficient(evidence: Evidence) -> AnalysisResultOut:
    """The result of a run that had nothing to send (no provider call is made)."""
    return validate(ParsedOutput(), evidence)
