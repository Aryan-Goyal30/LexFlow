"""A scripted stand-in for an assessment model (Phase 7 demo). It is **not AI**.

It builds a fixed-shape answer from the inputs it is given so that the whole
workflow (gate, validation, storage, review, brief, screens) can be shown and
tested without contacting any provider. Every sentence it writes starts with
"[Scripted]". Its stances are assigned by position, not by reading the law:
the first accepted precedent "supports", the second "cuts against", any
further one "does not resolve".

Like the Phase 5 double, it also cites a precedent that does not exist and
adds a reasoning step that rests on no accepted finding; validation must
remove both, which the demo then shows as removed items.
"""

from __future__ import annotations

import json

from lexflow.analysis.provider import Response
from lexflow.analysis.scripted import _quote
from lexflow.assessment.provider import AssessmentRequest

MODEL = "scripted-assessment-v1"
_STANCES = ("supports", "cuts_against")
_WORDS = {
    "supports": "is read as supporting",
    "cuts_against": "is read as cutting against",
    "does_not_resolve": "is read as not resolving",
}


class ScriptedAssessmentProvider:
    name = "scripted"
    model = MODEL

    def generate(self, request: AssessmentRequest) -> Response:
        inputs = request.inputs
        precedents = []
        for i, p in enumerate(inputs.precedents):
            stance = _STANCES[i] if i < len(_STANCES) else "does_not_resolve"
            precedents.append(
                {
                    "precedent": p.id,
                    "stance": stance,
                    "quote": _quote(p.text),
                    "explanation": (
                        f"[Scripted] For this demonstration, {p.id} {_WORDS[stance]} the "
                        "position in the accepted findings. A test double assigned this "
                        "reading by position; it is not a legal analysis."
                    ),
                }
            )
        # Cites a precedent that was never accepted: validation must remove it.
        precedents.append(
            {
                "precedent": "P99",
                "stance": "supports",
                "quote": "This passage does not exist in any judgment.",
                "explanation": "[Scripted] A citation of a precedent that is not an input.",
            }
        )
        findings = [f.id for f in inputs.findings[:3]]
        reasoning = []
        for p in inputs.precedents[:2]:
            reasoning.append(
                {
                    "text": (
                        f"[Scripted] The accepted findings {', '.join(findings)} are read "
                        f"together with the passage of {p.id}."
                    ),
                    "findings": findings,
                    "precedents": [p.id],
                }
            )
        # Rests on a finding that does not exist: validation must remove it.
        reasoning.append(
            {
                "text": "[Scripted] A step that rests on a finding nobody accepted.",
                "findings": ["F99"],
                "precedents": [],
            }
        )
        uncertainty = "mixed_evidence" if len(inputs.precedents) >= 2 else "limited_support"
        answer = {
            "summary": (
                f"[Scripted] Demonstration assessment built from {len(inputs.findings)} accepted "
                f"findings and {len(inputs.precedents)} accepted precedent comparisons. It was "
                "written by a test double, not by AI, and it is not legal advice."
            ),
            "uncertainty": uncertainty,
            "precedents": precedents,
            "reasoning": reasoning,
            "missing_evidence": [
                "[Scripted] Judgments from an approved source: this demonstration uses "
                "synthetic test judgments only."
            ],
            "limitations": [
                "[Scripted] Stances were assigned by position to demonstrate the workflow."
            ],
        }
        return Response(text=json.dumps(answer), usage={})
