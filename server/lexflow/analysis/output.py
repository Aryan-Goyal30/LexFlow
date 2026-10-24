"""The JSON the model is asked to return, and how it is read.

``RESPONSE_SCHEMA`` is sent to the provider as the structured-output schema.
Whatever comes back is parsed here regardless: a provider's adherence to a
schema is never trusted. The whole answer must be a JSON object with the
expected lists; within the lists, an item that does not fit its shape is
dropped and counted (``malformed``), not allowed to sink the other items.

Where each constraint lives (decided in M9, 2026-10-24):

- the **provider schema** carries types, required keys and the shape of each
  item, the subset every structured-output API accepts. Limits (list sizes,
  string lengths, id formats) are stated there in ``description`` text only,
  because a size keyword was the suspect in a provider rejection (M8e);
- the **application** enforces every limit here (the pydantic models and the
  per-list maxima) and, in ``validation.py``, every grounding rule. Nothing
  was relaxed in the application when the provider schema was simplified.

Versions: ``prompt.PROMPT_VERSION`` names the instructions and evidence
layout (``case-analysis-v2`` from M10). ``RESPONSE_SCHEMA_VERSION`` names
this schema: ``case-analysis-schema-1`` had ``minItems``/``maxItems`` (runs
before 2026-10-20), ``case-analysis-schema-2`` states sizes in descriptions.
Runs record the versions they used from M9 on; older runs have no record and
are not reinterpreted.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

MAX_FACTS = 40
MAX_ISSUES = 20
MAX_PRECEDENTS = 20
MAX_CONTRADICTIONS = 15
STATEMENT_MAX = 600
QUESTION_MAX = 400
QUOTE_MAX = 300
SUMMARY_MAX = 800
POINT_MAX = 300
POINTS_MAX = 5

EVIDENCE_ID = re.compile(r"[DJ][1-9][0-9]{0,3}")
FACT_ID = re.compile(r"F[1-9][0-9]{0,3}")

# Keys that would carry an outcome prediction (Phase 7, gated): never asked
# for, discarded if present.
OUTCOME_KEYS = frozenset({"outcome_assessment", "outcomeAssessment", "outcome", "prediction"})


class _Item(BaseModel):
    # Unknown keys inside an item are ignored; the item's known fields are checked.
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class ModelFact(_Item):
    id: str = Field(pattern=FACT_ID.pattern)
    statement: str = Field(min_length=1, max_length=STATEMENT_MAX)
    evidence: str = Field(min_length=2, max_length=6)
    quote: str = Field(min_length=1, max_length=QUOTE_MAX)


class ModelIssue(_Item):
    question: str = Field(min_length=1, max_length=QUESTION_MAX)
    fact_ids: list[str] = Field(default_factory=list, max_length=20)


class ModelPrecedent(_Item):
    evidence: str = Field(min_length=2, max_length=6)
    summary: str = Field(min_length=1, max_length=SUMMARY_MAX)
    similarities: list[str] = Field(default_factory=list, max_length=POINTS_MAX)
    differences: list[str] = Field(default_factory=list, max_length=POINTS_MAX)


class ModelSource(_Item):
    evidence: str = Field(min_length=2, max_length=6)
    quote: str = Field(min_length=1, max_length=QUOTE_MAX)


class ModelContradiction(_Item):
    description: str = Field(min_length=1, max_length=STATEMENT_MAX)
    sources: list[ModelSource] = Field(min_length=2, max_length=4)


@dataclass
class ParsedOutput:
    facts: list[ModelFact] = field(default_factory=list)
    issues: list[ModelIssue] = field(default_factory=list)
    precedents: list[ModelPrecedent] = field(default_factory=list)
    contradictions: list[ModelContradiction] = field(default_factory=list)
    insufficient_evidence: bool = False
    malformed: int = 0  # items dropped because they did not fit their shape
    over_limit: int = 0  # items beyond the per-list maximum
    outcome_discarded: bool = False


class InvalidOutputError(Exception):
    """The answer as a whole is unusable (not JSON, not an object, wrong types)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _strip_fence(text: str) -> str:
    # Some models wrap JSON in a Markdown code fence despite the JSON mime type.
    stripped = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    return match.group(1) if match else stripped


def _items[T: BaseModel](
    raw: Any, model: type[T], maximum: int, out: ParsedOutput, name: str
) -> list[T]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise InvalidOutputError("invalid-output", f"'{name}' is not a list.")
    kept: list[T] = []
    for item in raw:
        if len(kept) == maximum:
            out.over_limit += 1
            continue
        try:
            kept.append(model.model_validate(item))
        except ValidationError:
            out.malformed += 1
    return kept


def parse(text: str) -> ParsedOutput:
    """Read the model's answer. Raises ``InvalidOutputError`` if it is unusable as a whole."""
    try:
        data = json.loads(_strip_fence(text))
    except (json.JSONDecodeError, RecursionError):
        raise InvalidOutputError("invalid-output", "The answer was not valid JSON.") from None
    if not isinstance(data, dict):
        raise InvalidOutputError("invalid-output", "The answer was not a JSON object.")
    out = ParsedOutput()
    out.outcome_discarded = any(key in data for key in OUTCOME_KEYS)
    out.facts = _items(data.get("facts"), ModelFact, MAX_FACTS, out, "facts")
    out.issues = _items(data.get("issues"), ModelIssue, MAX_ISSUES, out, "issues")
    out.precedents = _items(
        data.get("precedents"), ModelPrecedent, MAX_PRECEDENTS, out, "precedents"
    )
    out.contradictions = _items(
        data.get("contradictions"), ModelContradiction, MAX_CONTRADICTIONS, out, "contradictions"
    )
    flag = data.get("insufficient_evidence", False)
    if not isinstance(flag, bool):
        raise InvalidOutputError("invalid-output", "'insufficient_evidence' is not true or false.")
    out.insufficient_evidence = flag
    return out


def _string(max_length: int) -> dict[str, Any]:
    # Lengths and item counts go in the description, not in keywords: providers
    # support different subsets of JSON Schema (an array-size keyword made the
    # schema a suspect for a provider rejection), and the parser above enforces
    # every limit anyway.
    return {"type": "string", "description": f"At most {max_length} characters."}


def _strings(max_items: int, max_length: int) -> dict[str, Any]:
    return {
        "type": "array",
        "description": f"At most {max_items} items.",
        "items": _string(max_length),
    }


# A plain JSON Schema (no $ref, no string lengths, no array sizes), within the
# subset that structured-output APIs accept.
RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "description": f"At most {MAX_FACTS} facts.",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "F1, F2, ..."},
                    "statement": _string(STATEMENT_MAX),
                    "evidence": {"type": "string", "description": "One passage id, e.g. D3."},
                    "quote": {
                        "type": "string",
                        "description": "Copied exactly from that passage; at most 200 characters.",
                    },
                },
                "required": ["id", "statement", "evidence", "quote"],
            },
        },
        "issues": {
            "type": "array",
            "description": f"At most {MAX_ISSUES} issues.",
            "items": {
                "type": "object",
                "properties": {
                    "question": _string(QUESTION_MAX),
                    "fact_ids": _strings(20, 6),
                },
                "required": ["question", "fact_ids"],
            },
        },
        "precedents": {
            "type": "array",
            "description": f"At most {MAX_PRECEDENTS} precedents.",
            "items": {
                "type": "object",
                "properties": {
                    "evidence": {"type": "string", "description": "One judgment id, e.g. J1."},
                    "summary": _string(SUMMARY_MAX),
                    "similarities": _strings(POINTS_MAX, POINT_MAX),
                    "differences": _strings(POINTS_MAX, POINT_MAX),
                },
                "required": ["evidence", "summary", "similarities", "differences"],
            },
        },
        "contradictions": {
            "type": "array",
            "description": f"At most {MAX_CONTRADICTIONS} contradictions.",
            "items": {
                "type": "object",
                "properties": {
                    "description": _string(STATEMENT_MAX),
                    "sources": {
                        "type": "array",
                        "description": "Two to four sources.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "evidence": {"type": "string"},
                                "quote": _string(QUOTE_MAX),
                            },
                            "required": ["evidence", "quote"],
                        },
                    },
                },
                "required": ["description", "sources"],
            },
        },
        "insufficient_evidence": {"type": "boolean"},
    },
    "required": ["facts", "issues", "precedents", "contradictions", "insufficient_evidence"],
}

RESPONSE_SCHEMA_VERSION = "case-analysis-schema-2"


def schema_sha256() -> str:
    """A fingerprint of ``RESPONSE_SCHEMA`` (canonical JSON), stored with each
    run so a silent schema change under the same version name is detectable."""
    canonical = json.dumps(RESPONSE_SCHEMA, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
