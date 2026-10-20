"""A scripted stand-in for the model, for automated tests and the e2e app only.

It is **not AI**: it builds a fixed-shape answer from the evidence it is given
(quoting the first words of passages) so that the whole pipeline - queue,
worker, validation, storage, screens and source links - can be tested
without contacting Google. Every statement it writes starts with
"[Scripted]", its provider name is "scripted", and the settings refuse
``LEXFLOW_AI_PROVIDER=scripted`` unless the database is a test or e2e
database (``lexflow.config``). It also adds one fact citing evidence that
does not exist, which validation must remove.
"""

from __future__ import annotations

import json

from lexflow.analysis.provider import Request, Response

MODEL = "scripted-v1"
QUOTE_CHARS = 120


def _quote(text: str) -> str:
    """The passage's first words, cut at a word boundary, copied exactly."""
    head = text.strip()[:QUOTE_CHARS]
    if len(text.strip()) > QUOTE_CHARS and " " in head:
        head = head[: head.rindex(" ")]
    return head.strip()


class ScriptedProvider:
    name = "scripted"
    model = MODEL

    def generate(self, request: Request) -> Response:
        evidence = request.evidence
        facts = [
            {
                "id": f"F{i}",
                "statement": f'[Scripted] Passage {p.id} of "{p.document_name}" begins as quoted.',
                "evidence": p.id,
                "quote": _quote(p.text),
            }
            for i, p in enumerate(evidence.passages[:3], start=1)
            if _quote(p.text)
        ]
        # Cites evidence that was never sent: validation must remove it.
        facts.append(
            {
                "id": f"F{len(facts) + 1}",
                "statement": "[Scripted] A fact citing a passage that does not exist.",
                "evidence": "D999",
                "quote": "This quote is not in any passage.",
            }
        )
        issues = (
            [
                {
                    "question": "[Scripted] Which of these facts does the other side dispute?",
                    "fact_ids": ["F1"],
                }
            ]
            if len(facts) > 1
            else []
        )
        precedents = [
            {
                "evidence": j.id,
                "summary": f'[Scripted] The passage of "{j.title}" begins: {_quote(j.text)}',
                "similarities": ["[Scripted] Retrieved by keyword overlap with the case."],
                "differences": ["[Scripted] Not compared: this is a test double, not AI."],
            }
            for j in evidence.judgments[:2]
        ]
        passages = evidence.passages
        contradictions = (
            [
                {
                    "description": "[Scripted] Two passages shown side by side for comparison.",
                    "sources": [
                        {"evidence": passages[0].id, "quote": _quote(passages[0].text)},
                        {"evidence": passages[1].id, "quote": _quote(passages[1].text)},
                    ],
                }
            ]
            if len(passages) >= 2 and _quote(passages[0].text) and _quote(passages[1].text)
            else []
        )
        answer = {
            "facts": facts,
            "issues": issues,
            "precedents": precedents,
            "contradictions": contradictions,
            "insufficient_evidence": not passages,
        }
        return Response(text=json.dumps(answer), usage={})
