"""Checks every item of a model's answer against the run's evidence.

What survives, and only that, is stored and shown:

- a **fact** cites exactly one case passage (``D`` id) that was sent in this
  run, and its quote occurs in that passage (after Unicode and whitespace
  normalisation, at least ``QUOTE_MIN`` characters); otherwise it is removed;
- a **precedent** cites a judgment passage (``J`` id) retrieved for this run;
  one citing any other judgment is rejected (the brief: "an output citing an
  unknown judgment is rejected"). Its title, court and citation come from the
  collection, never from the model;
- a **contradiction** needs at least two distinct verified sources: two
  quotes that are the same text, or one quote inside another from the same
  passage, count once;
- an **issue** keeps only references to surviving facts and is removed when
  none are left;
- any item whose wording names a law-report or neutral citation that occurs
  nowhere in the evidence is removed (an invented citation cannot hide in
  prose), and so is one naming a case ("A v. B") neither of whose parties
  appears in the evidence, the case title or a retrieved judgment's title;
- an outcome assessment is never shown (Phase 7): it is counted if returned
  as a key, and an item whose wording predicts how the case, a claim, an
  appeal or a relief will end ("is likely to win the suit", "the court will
  grant an injunction", "prospects of success") is removed. An outcome verb
  with an ordinary object stays: "is likely to lose goodwill", "may lose
  sales" and "could win a tender" are facts, not predictions.

The case-name and outcome-wording checks are deliberately simple patterns.
They remove the clear cases and can miss paraphrases ("the plaintiff's
position looks stronger") or invented cases written without "v."; they can
also remove an unusual factual sentence that reads like a prediction. That
limit is documented, not hidden: the patterns cannot tell a legal prediction
from a fact in every wording.

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
# Changes whenever the rules below change. "grounding-1": M4 to M8;
# "grounding-2": M9 (neutral citations, case names, outcome wording,
# distinct contradiction sources); "grounding-3": M9 review (outcome wording
# narrowed to litigation outcomes, so factual statements are kept).
VALIDATOR_VERSION = "grounding-3"

REASONS: dict[str, str] = {
    "unknown-evidence": "Cited a passage that was not part of this analysis's evidence.",
    "quote-not-found": "Its quote does not occur in the passage it cites.",
    "quote-too-short": f"Its quote was shorter than {QUOTE_MIN} characters, too short to verify.",
    "unknown-judgment": "Cited a judgment that was not retrieved for this analysis.",
    "unverified-citation": "Named a citation or case that does not appear in the evidence.",
    "outcome-wording": "Predicted the outcome or its chances; LexFlow does not show that.",
    "issue-without-facts": "Did not rest on any verified fact.",
    "contradiction-unsupported": "Had fewer than two distinct verified sources.",
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
    # Neutral citations: "2023 INSC 456", "2024:DHC:1234".
    r"|\b\d{4}\s+INSC\s+\d+"
    r"|\b\d{4}:[A-Z]{2,6}:\d+"
)

# "A v. B", "A vs B", "A versus B" with capitalised party names.
_PARTY = r"[A-Z][\w.&'-]*(?:\s+(?:[A-Z][\w.&'-]*|of|and|&|the)){0,6}"
_CASE_NAME = re.compile(rf"\b({_PARTY})\s+(?:v\.?|vs\.?|versus)\s+({_PARTY})")
# Words that say nothing about which case is meant.
_GENERIC_WORDS = (
    "the and of state union india government republic plaintiff plaintiffs defendant "
    "defendants petitioner petitioners respondent respondents appellant appellants "
    "applicant accused complainant others anr ors another mr ms mrs m/s ltd pvt private "
    "limited company co corp inc llp bank court see per following like also cf held "
    "under"
)
_GENERIC = frozenset(_GENERIC_WORDS.split())
_WORD = re.compile(r"[a-z][a-z0-9'-]{2,}")

# Wording that predicts how the case ends (Phase 7 is gated). Each pattern
# needs a predictive word and a litigation outcome: the case, a claim, an
# appeal or a relief, a court's disposition, or an outcome verb with nothing
# after it. "Likely to lose goodwill" or "could win a tender" does not match.
_PREDICT = (
    r"(?:(?:un)?likely\s+to|probably|expected\s+to|bound\s+to|going\s+to|certain\s+to|"
    r"sure\s+to|will|would|should|shall)"
)
_LITIGATION = (
    r"(?:case|suit|claim|claims|appeal|petition|application|action|matter|proceedings?|"
    r"litigation|trial|dispute|challenge|plaint|complaint|writ|prosecution|defen[cs]e)"
)
_RELIEF = (
    r"(?:injunction|damages|compensation|costs|relief|remedy|decree|order|prayer|"
    r"possession|arrears|maintenance|bail|acquittal|conviction)"
)
_COURT = r"(?:court|tribunal|judge|bench|forum|commission)"
_ARTICLE = r"(?:(?:the|this|that|its|their|his|her|our|an|a)\s+)?"
_ANY = r"(?:[\w'-]+\s+)"
_BARE_END = r"(?=\s*(?:[.;:,!?)]|$)"
_OUTCOME = re.compile(
    "|".join(
        (
            # "is likely to win the suit", "will succeed in its claim"
            rf"\b{_PREDICT}\s+{_ANY}{{0,2}}?(?:win|lose|succeed|prevail|fail)\s+"
            rf"(?:(?:in|on|at|with)\s+)?{_ARTICLE}{_ANY}{{0,2}}?{_LITIGATION}\b",
            # a bare result: "is likely to succeed.", "will certainly lose on the notice"
            rf"\b{_PREDICT}\s+{_ANY}{{0,2}}?(?:win|lose|succeed|prevail){_BARE_END}"
            r"|\s+(?:on|at|because|since|as|given|if|unless|against|before)\b)",
            # "the suit is likely to fail", "the appeal will probably be dismissed"
            rf"\b{_LITIGATION}\s+(?:(?:is|are)\s+)?{_PREDICT}\s+{_ANY}?(?:fail|succeed|be\s+"
            r"(?:dismissed|allowed|decreed|granted|rejected|refused|quashed|upheld|set\s+aside))\b",
            # "the court will grant an injunction", "the court is likely to dismiss the suit"
            rf"\b{_COURT}\s+(?:(?:is|are)\s+)?{_PREDICT}\s+{_ANY}?(?:grant|award|allow|dismiss|"
            rf"reject|refuse|decree|quash|uphold|set\s+aside)\s+{_ARTICLE}{_ANY}{{0,2}}?"
            rf"(?:{_RELIEF}|{_LITIGATION})\b",
            # "the court will rule in favour of the plaintiff", "will side with the defendant"
            rf"\b{_COURT}\s+(?:(?:is|are)\s+)?{_PREDICT}\s+{_ANY}?(?:rule|decide|find|hold|side)\s+"
            rf"(?:in\s+{_ANY}{{0,3}}?favou?r|with\s+the\s+(?:plaintiff|defendant|petitioner|"
            r"respondent|appellant|applicant|complainant|accused))",
            # "chances of success", "prospects of winning the appeal", "odds of winning are low"
            rf"\b(?:chances?|likelihood|probability|odds|prospects?)\s+of\s+{_ANY}{{0,2}}?"
            rf"(?:success|succeeding|prevailing|(?:winning|losing)(?:\s+{_ARTICLE}{_ANY}{{0,2}}?"
            rf"{_LITIGATION}\b|{_BARE_END}|\s+(?:are|is|was|were|look|looks|seem|seems|"
            r"remain|remains|on|at)\b)))",
            # "a 70% chance of recovering the arrears" (not "a 70% probability that it is forged")
            rf"\b\d{{1,3}}\s?(?:%|per\s?cent)\s+(?:chance|probability|likelihood)\b[^.;]{{0,40}}?"
            rf"\b(?:win|winning|lose|losing|succeed|success|prevail|recover|recovering|{_RELIEF})\b",
        )
    ),
    re.IGNORECASE,
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
        known += [normalise(j.title) for j in evidence.judgments]
        context = evidence.context
        known += [normalise(t) for t in (context.title, context.opposing_party or "") if t]
        self._known_text = "\n".join(known)
        self._known_words = set(_WORD.findall(self._known_text.lower()))

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

    def _unknown_party(self, party: str) -> bool:
        words = [w for w in _WORD.findall(party.lower()) if w not in _GENERIC]
        return bool(words) and not any(w in self._known_words for w in words)

    def invented_citation(self, *texts: str) -> bool:
        for text in texts:
            plain = normalise(text)
            for match in _CITATION.finditer(plain):
                if match.group(0) not in self._known_text:
                    return True
            for match in _CASE_NAME.finditer(plain):
                if match.group(0) in self._known_text:
                    continue
                if self._unknown_party(match.group(1)) or self._unknown_party(match.group(2)):
                    return True
        return False

    def outcome_wording(self, *texts: str) -> bool:
        return any(_OUTCOME.search(normalise(text)) for text in texts)

    def rejected_prose(self, *texts: str) -> str | None:
        """The reason code for prose that may not be shown, or None."""
        if self.invented_citation(*texts):
            return "unverified-citation"
        if self.outcome_wording(*texts):
            return "outcome-wording"
        return None


def _same_source(a: AnalysisSourceOut, b: AnalysisSourceOut) -> bool:
    """Two sources that cannot disagree: the same text, or (in one passage) one
    quote inside the other."""
    if a.quote == b.quote:
        return True
    return a.evidence_id == b.evidence_id and (a.quote in b.quote or b.quote in a.quote)


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
        prose = check.rejected_prose(fact.statement)
        if prose is not None:
            tally.remove(prose)
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
        prose = check.rejected_prose(issue.question)
        if prose is not None:
            tally.remove(prose)
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
        prose = check.rejected_prose(item.summary, *item.similarities, *item.differences)
        if prose is not None:
            tally.remove(prose)
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
            if isinstance(source, AnalysisSourceOut) and not any(
                _same_source(s, source) for s in sources
            ):
                sources.append(source)
        if len(sources) < 2:
            tally.remove("contradiction-unsupported")
            continue
        prose = check.rejected_prose(contradiction.description)
        if prose is not None:
            tally.remove(prose)
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
