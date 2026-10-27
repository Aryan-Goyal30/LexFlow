"""Prepared demonstration analysis: written in advance for one fictional case. **Not AI.**

``LEXFLOW_AI_PROVIDER=prepared`` answers only for a case whose title matches a
prepared script in ``lexflow/analysis/prepared/`` (the fictional academic
matter *Aarav Foods Pvt. Ltd. v. Sunrise Retail Pvt. Ltd.*). Every other case
gets "insufficient evidence" and no findings. Nothing leaves this computer, so
the sample-cases-only rule for external providers (D1) does not apply to it
(``client_data_allowed``); it still applies in full to Gemini.

The script names the document or judgment and the exact words each finding
rests on. At run time those words are looked up in the passages the analysis
actually assembled (the uploaded documents' extracted text, and the judgment
chunks pinned by ``pinned_judgments``), and the passage's own text is quoted.
The answer then goes through the same validation as any model's: a finding
whose words are not in its passage is removed, never shown.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import cache
from pathlib import Path
from typing import Any

from lexflow.analysis.evidence import Evidence, JudgmentPassage, Passage
from lexflow.analysis.provider import Request, Response

MODEL = "prepared-demo-v1"
SCRIPTS = Path(__file__).with_name("prepared")
_SPACE = re.compile(r"\s+")
_TYPOGRAPHY = str.maketrans({0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"'})


def _normal(text: str) -> str:
    return _SPACE.sub(" ", unicodedata.normalize("NFKC", text).translate(_TYPOGRAPHY)).strip()


def _key(title: str) -> str:
    return _normal(title).casefold()


@cache
def scripts() -> dict[str, dict[str, Any]]:
    """Prepared scripts by case title (normalised)."""
    found: dict[str, dict[str, Any]] = {}
    for path in sorted(SCRIPTS.glob("*.json")):
        script = json.loads(path.read_text(encoding="utf-8"))
        for title in script["case_titles"]:
            found[_key(title)] = script
    return found


def script_for(case_title: str) -> dict[str, Any] | None:
    return scripts().get(_key(case_title))


def pinned_judgments(case_title: str) -> tuple[tuple[str, str], ...]:
    """(judgment title prefix, words) the analysis must include as judgment passages."""
    script = script_for(case_title)
    if script is None:
        return ()
    return tuple((p["judgment"], p["quote"]) for p in script.get("precedents", []))


def _exact(passage_text: str, words: str) -> str | None:
    """The passage's own wording of ``words`` (spacing and quote marks may differ)."""
    target = _normal(words)
    if target not in _normal(passage_text):
        return None
    text = unicodedata.normalize("NFKC", passage_text).translate(_TYPOGRAPHY)
    match = re.search(r"\s+".join(re.escape(t) for t in target.split(" ")), text)
    return None if match is None else text[match.start() : match.end()]


def _find_document(evidence: Evidence, document: str, words: str) -> tuple[Passage, str] | None:
    candidates = sorted(evidence.passages, key=lambda p: p.document_name != document)
    for passage in candidates:
        quote = _exact(passage.text, words)
        if quote is not None:
            return passage, quote
    return None


def _find_judgment(
    evidence: Evidence, judgment: str, words: str
) -> tuple[JudgmentPassage, str] | None:
    for passage in evidence.judgments:
        if _key(passage.title).startswith(_key(judgment)):
            quote = _exact(passage.text, words)
            if quote is not None:
                return passage, quote
    return None


class PreparedProvider:
    name = "prepared"
    model = MODEL

    def generate(self, request: Request) -> Response:
        evidence = request.evidence
        script = script_for(evidence.context.title)
        if script is None:
            empty: dict[str, Any] = {
                "facts": [],
                "issues": [],
                "precedents": [],
                "contradictions": [],
                "insufficient_evidence": True,
            }
            return Response(text=json.dumps(empty), usage={})

        facts: list[dict[str, Any]] = []
        ids: dict[str, str] = {}
        for item in script["facts"]:
            found = _find_document(evidence, item["document"], item["quote"])
            if found is None:
                continue  # its document was not selected or not uploaded
            passage, quote = found
            ids[item["key"]] = f"F{len(facts) + 1}"
            facts.append(
                {
                    "id": ids[item["key"]],
                    "statement": item["statement"],
                    "evidence": passage.id,
                    "quote": quote,
                }
            )

        issues = []
        for item in script["issues"]:
            refs = [ids[k] for k in item["facts"] if k in ids]
            if refs:
                issues.append({"question": item["question"], "fact_ids": refs})

        precedents = []
        for item in script["precedents"]:
            found_j = _find_judgment(evidence, item["judgment"], item["quote"])
            if found_j is None:
                continue
            passage_j, quote = found_j
            precedents.append(
                {
                    "evidence": passage_j.id,
                    "summary": item["summary"],
                    "quote": quote,
                    "similarities": item["similarities"],
                    "differences": item["differences"],
                }
            )

        contradictions = []
        for item in script["contradictions"]:
            found_all = [
                _find_document(evidence, s["document"], s["quote"]) for s in item["sources"]
            ]
            sources = [f for f in found_all if f is not None]
            if len(sources) == len(found_all):
                contradictions.append(
                    {
                        "description": item["description"],
                        "sources": [{"evidence": p.id, "quote": q} for p, q in sources],
                    }
                )

        answer = {
            "facts": facts,
            "issues": issues,
            "precedents": precedents,
            "contradictions": contradictions,
            "insufficient_evidence": not facts,
        }
        return Response(text=json.dumps(answer), usage={})
