"""Strict checks of an assessment against its inputs (D7-5, ``assessment-grounding-1``).

What survives, and only that, is stored and shown:

- a **cited precedent** must be an accepted precedent comparison of the run
  whose passage is unchanged (``inputs.gather``); its quote must occur in that
  passage under Phase 5's quote rules (normalised, at least ``QUOTE_MIN``
  characters per piece, pieces in order); otherwise it is removed. Title,
  court, citation, year and the synthetic flag come from the collection,
  never from the answer;
- a **reasoning step** must name at least one reference, and every reference
  must be an accepted finding of the run or a precedent that survived;
  otherwise the whole step is removed (a step resting on a rejected,
  unreviewed or invented finding is unsupported);
- **prose** (summary, explanations, steps, missing evidence, limitations) is
  rejected when it states a probability, percentage, odds or chance; predicts
  how the case ends or what a court will do (Phase 5's outcome patterns plus
  "will certainly", "guaranteed to", "the court will hold"); names a citation
  or case that is not among the inputs; or, when a cited judgment is
  synthetic, presents it as real or binding law;
- a rejected **summary withholds the whole assessment**: nothing of a
  misleading answer is shown (strict rejection over cleanup);
- the **uncertainty category** must fit the stances that survived (both
  supporting and adverse precedents: mixed or limited; only supporting:
  supports or limited; only adverse: limited; none resolving: insufficient).
  Otherwise it is lowered to a consistent category and counted. The
  category "insufficient_basis" always stays available: caution is never
  overridden;
- with no surviving precedent, no surviving reasoning step, or the category
  "insufficient_basis", the assessment is ``insufficient``, with the reason.

Each removal is counted by reason code; no text is logged. As in Phase 5 the
prose patterns are deliberately simple: they remove the clear cases and can
miss paraphrases ("the position looks stronger") or catch an unusual
sentence. They establish provenance and keep forbidden forms out; they do
not make a reading legally right. The lawyer's review is required.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from lexflow.analysis.validation import (
    _CASE_NAME,
    _CITATION,
    _ELISION,
    _GENERIC,
    _OUTCOME,
    _WORD,
    QUOTE_MIN,
    QUOTE_PIECES_MAX,
    _find_in_order,
    normalise,
)
from lexflow.assessment.inputs import InputPrecedent, Inputs
from lexflow.assessment.output import FINDING_REF, PRECEDENT_REF, ParsedAssessment
from lexflow.schemas import (
    AnalysisPassageRefOut,
    AnalysisRemovedOut,
    AnalysisRemovedReasonOut,
    AssessmentPrecedentOut,
    AssessmentResultOut,
    AssessmentStepOut,
)

VALIDATOR_VERSION = "assessment-grounding-1"

REASONS: dict[str, str] = {
    "malformed": "Did not have the expected shape.",
    "over-limit": "Went beyond the number of items allowed.",
    "unexpected-field": "Returned a field the contract does not have (such as a score); ignored.",
    "unknown-precedent": "Cited a precedent that is not an accepted comparison of this analysis.",
    "duplicate": "Repeated a precedent already cited.",
    "quote-not-found": "Its quote does not occur in the judgment passage it cites.",
    "quote-too-short": f"Its quote was shorter than {QUOTE_MIN} characters, too short to verify.",
    "unsupported-step": "A reasoning step did not rest on accepted findings or cited precedents.",
    "probability-language": "Stated a probability, percentage, odds or chance; never shown.",
    "outcome-wording": "Predicted the outcome or what a court will do; never shown.",
    "unverified-citation": "Named a citation or case that is not among the inputs.",
    "synthetic-misrepresented": "Presented a synthetic (fictional) judgment as real law.",
    "uncertainty-adjusted": "The uncertainty category did not fit the cited precedents; lowered.",
}

INSUFFICIENT: dict[str, str] = {
    "summary-withheld": (
        "The assessment's summary stated a probability, a predicted outcome, an unknown "
        "citation or presented fictional law as real, so nothing from it is shown."
    ),
    "no-verified-precedent": (
        "No cited precedent could be verified against the accepted precedent comparisons, so "
        "no assessment is shown."
    ),
    "no-supported-reasoning": (
        "No reasoning step rested on accepted findings or verified precedents, so no "
        "assessment is shown."
    ),
    "assessed-insufficient": (
        "The accepted findings and precedents do not give a sufficient basis for an assessment."
    ),
}

_PROBABILITY = re.compile(
    "|".join(
        (
            r"\d+(?:\.\d+)?\s*(?:%|per\s?cent\b|percent\b)",
            r"\b(?:probability|probabilities|percentage|percentages|win\s+rate|success\s+rate)\b",
            # "at odds with" is ordinary wording; "the odds are" is not.
            r"(?<!\bat\s)\bodds\b",
            # "likelihood of confusion" is a test in trade mark law, not a forecast.
            r"\blikelihood\b(?!\s+of\s+(?:confusion|deception|association))",
            r"\bchances?\s+(?:of|that|to)\s+(?:[\w'-]+\s+){0,3}?(?:win|winning|succeed|succeeding|"
            r"success|prevail|prevailing|lose|losing|favou?rable)\b",
            # "3 out of 4", "9 in 10 cases" (not "Order 39 in 2017")
            r"\b\d+\s+out\s+of\s+\d+\b",
            r"\b\d+\s+in\s+\d+\s+(?:cases|matters|suits|appeals|times|chances?|instances)\b",
        )
    ),
    re.IGNORECASE,
)
_DEFINITIVE = re.compile(
    "|".join(
        (
            r"\b(?:will|shall|must)\s+(?:certainly|definitely|surely|undoubtedly|inevitably)\b",
            r"\b(?:certain|guaranteed|bound|sure)\s+to\s+(?:win|lose|succeed|fail|prevail|be\s+"
            r"(?:allowed|dismissed|decreed|granted|rejected|refused|quashed|upheld))\b",
            r"\bguaranteed\s+(?:outcome|win|success|result|victory)\b",
            r"\b(?:court|tribunal|judge|bench)\s+(?:will|shall|must)\s+(?:rule|hold|find|decide|"
            r"grant|dismiss|allow|reject|decree|award|accept|uphold|quash)\b",
        )
    ),
    re.IGNORECASE,
)
_CALLED_REAL = re.compile(
    r"\b(?:real|genuine|actual|reported|binding|authoritative)\s+(?:judgments?|judgements?|"
    r"cases?|precedents?|authority|authorities|decisions?|law)\b"
    r"|\bnot\s+(?:fictional|synthetic|invented|a\s+test)\b|\bgood\s+law\b|\bsettled\s+law\b"
    r"|\bbinding\s+(?:on|upon)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Verdict:
    status: str  # "ready" or "insufficient"
    result: AssessmentResultOut | None
    reason_code: str | None
    reason: str | None
    removed: AnalysisRemovedOut


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
    def __init__(self, inputs: Inputs) -> None:
        known = [normalise(p.text) for p in inputs.precedents]
        known += [normalise(p.title) for p in inputs.precedents]
        known += [normalise(p.citation) for p in inputs.precedents if p.citation]
        known += [normalise(p.summary) for p in inputs.precedents]
        known += [normalise(f.text) for f in inputs.findings]
        self._known_text = "\n".join(known)
        self._known_words = set(_WORD.findall(self._known_text.lower()))
        self._synthetic = any(p.synthetic for p in inputs.precedents)

    def quote(self, precedent: InputPrecedent, quote: str) -> str | None:
        """None when the quote verifies, else the reason code."""
        pieces = [piece for piece in _ELISION.split(normalise(quote)) if piece]
        if not pieces or any(len(piece) < QUOTE_MIN for piece in pieces):
            return "quote-too-short"
        if len(pieces) > QUOTE_PIECES_MAX:
            return "quote-not-found"
        if _find_in_order(normalise(precedent.text), pieces) is None:
            return "quote-not-found"
        return None

    def _unknown_party(self, party: str) -> bool:
        words = [w for w in _WORD.findall(party.lower()) if w not in _GENERIC]
        return bool(words) and not any(w in self._known_words for w in words)

    def _invented_citation(self, plain: str) -> bool:
        for match in _CITATION.finditer(plain):
            if match.group(0) not in self._known_text:
                return True
        for match in _CASE_NAME.finditer(plain):
            if match.group(0) in self._known_text:
                continue
            if self._unknown_party(match.group(1)) or self._unknown_party(match.group(2)):
                return True
        return False

    def prose(self, *texts: str) -> str | None:
        """The reason code for prose that may not be shown, or None."""
        for text in texts:
            plain = normalise(text)
            if _PROBABILITY.search(plain):
                return "probability-language"
            if _OUTCOME.search(plain) or _DEFINITIVE.search(plain):
                return "outcome-wording"
            if self._invented_citation(plain):
                return "unverified-citation"
            if self._synthetic and _CALLED_REAL.search(plain):
                return "synthetic-misrepresented"
        return None


def _consistent(chosen: str, stances: list[str]) -> str:
    """The model's category if it fits the surviving stances, else the most
    conservative category that does. "insufficient_basis" always fits."""
    supports = "supports" in stances
    against = "cuts_against" in stances
    if supports and against:
        allowed, fallback = {"mixed_evidence", "limited_support"}, "mixed_evidence"
    elif supports:
        allowed, fallback = {"evidence_supports_position", "limited_support"}, "limited_support"
    elif against:
        allowed, fallback = {"limited_support"}, "limited_support"
    else:
        allowed, fallback = set(), "insufficient_basis"
    allowed.add("insufficient_basis")
    return chosen if chosen in allowed else fallback


def _insufficient(code: str, tally: _Tally) -> Verdict:
    return Verdict("insufficient", None, code, INSUFFICIENT[code], tally.result())


def validate(parsed: ParsedAssessment, inputs: Inputs, *, scripted: bool) -> Verdict:
    tally = _Tally()
    check = _Checker(inputs)
    tally.remove("malformed", parsed.malformed)
    tally.remove("over-limit", parsed.over_limit)
    tally.remove("unexpected-field", parsed.unexpected_fields)

    prose = check.prose(parsed.summary)
    if prose is not None:
        tally.remove(prose)
        return _insufficient("summary-withheld", tally)

    cited: list[AssessmentPrecedentOut] = []
    for item in parsed.precedents:
        precedent = (
            inputs.precedent(item.precedent) if PRECEDENT_REF.fullmatch(item.precedent) else None
        )
        if precedent is None:
            tally.remove("unknown-precedent")
            continue
        if any(c.ref == precedent.id for c in cited):
            tally.remove("duplicate")
            continue
        problem = check.quote(precedent, item.quote) or check.prose(item.explanation)
        if problem is not None:
            tally.remove(problem)
            continue
        cited.append(
            AssessmentPrecedentOut(
                ref=precedent.id,
                judgment_id=precedent.judgment_id,
                title=precedent.title,
                court=precedent.court,
                citation=precedent.citation,
                year=precedent.year,
                synthetic=precedent.synthetic,
                passage=AnalysisPassageRefOut(
                    chunk_id=precedent.chunk_id,
                    section_number=precedent.section_number,
                    page_number=precedent.page_number,
                ),
                stance=item.stance,
                quote=" … ".join(p for p in _ELISION.split(normalise(item.quote)) if p),
                explanation=item.explanation,
            )
        )

    accepted = inputs.finding_ids()
    kept_refs = {c.ref for c in cited}
    steps: list[AssessmentStepOut] = []
    for step in parsed.reasoning:
        findings = list(dict.fromkeys(step.findings))
        precedents = list(dict.fromkeys(step.precedents))
        supported = (
            bool(findings or precedents)
            and all(FINDING_REF.fullmatch(f) and f in accepted for f in findings)
            and all(p in kept_refs for p in precedents)
        )
        if not supported:
            tally.remove("unsupported-step")
            continue
        problem = check.prose(step.text)
        if problem is not None:
            tally.remove(problem)
            continue
        steps.append(
            AssessmentStepOut(
                id=f"R{len(steps) + 1}",
                text=step.text,
                finding_ids=findings,
                precedent_refs=precedents,
            )
        )

    def points(values: list[str]) -> list[str]:
        kept: list[str] = []
        for value in values:
            problem = check.prose(value)
            if problem is not None:
                tally.remove(problem)
            else:
                kept.append(value)
        return kept

    missing = points(parsed.missing_evidence)
    limitations = points(parsed.limitations)

    if not cited:
        return _insufficient("no-verified-precedent", tally)
    if not steps:
        return _insufficient("no-supported-reasoning", tally)
    uncertainty = _consistent(parsed.uncertainty, [c.stance for c in cited])
    if uncertainty != parsed.uncertainty:
        tally.remove("uncertainty-adjusted")
    if uncertainty == "insufficient_basis":
        return _insufficient("assessed-insufficient", tally)

    all_synthetic = all(c.synthetic for c in cited)
    result = AssessmentResultOut(
        label="decision-support",
        summary=parsed.summary,
        uncertainty=uncertainty,  # type: ignore[arg-type]  # checked by _consistent
        precedents=cited,
        reasoning=steps,
        missing_evidence=missing,
        limitations=limitations,
        all_precedents_synthetic=all_synthetic,
        demo_only=all_synthetic or scripted,
        removed=tally.result(),
    )
    return Verdict("ready", result, None, None, result.removed)
