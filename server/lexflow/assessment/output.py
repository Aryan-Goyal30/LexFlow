"""The JSON an assessment provider is asked to return, and how it is read (D7-4).

As in Phase 5 (``lexflow.analysis.output``), a provider's adherence to the
schema is never trusted: the answer is parsed here. The whole answer must be a
JSON object with a summary and a known uncertainty category; within the lists,
an item that does not fit its shape is dropped and counted (``malformed``).

There is deliberately **no numeric field** in the contract. Top-level keys
that are not part of it (a "probability", a "win_chance", a "synthetic": false
meant to relabel a fictional judgment) are discarded and counted
(``unexpected-field``); every label the result carries is set by the server.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from lexflow.analysis.output import InvalidOutputError
from lexflow.domain import ASSESSMENT_UNCERTAINTIES

SCHEMA_VERSION = "outcome-assessment-schema-1"
SUMMARY_MAX = 1_200
TEXT_MAX = 600
QUOTE_MAX = 300
POINT_MAX = 300
MAX_PRECEDENTS = 10
MAX_STEPS = 10
MAX_POINTS = 5
MAX_REFS = 10

PRECEDENT_REF = re.compile(r"P[1-9][0-9]{0,3}")
FINDING_REF = re.compile(r"[FIPC][1-9][0-9]{0,3}")
KNOWN_KEYS = frozenset(
    {"summary", "uncertainty", "precedents", "reasoning", "missing_evidence", "limitations"}
)


class _Item(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class ModelCitation(_Item):
    precedent: str = Field(min_length=2, max_length=6)
    stance: Literal["supports", "cuts_against", "does_not_resolve"]
    quote: str = Field(min_length=1, max_length=QUOTE_MAX)
    explanation: str = Field(min_length=1, max_length=TEXT_MAX)


class ModelStep(_Item):
    text: str = Field(min_length=1, max_length=TEXT_MAX)
    findings: list[str] = Field(default_factory=list, max_length=MAX_REFS)
    precedents: list[str] = Field(default_factory=list, max_length=MAX_REFS)


@dataclass
class ParsedAssessment:
    summary: str = ""
    uncertainty: str = "insufficient_basis"
    precedents: list[ModelCitation] = field(default_factory=list)
    reasoning: list[ModelStep] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    malformed: int = 0
    over_limit: int = 0
    unexpected_fields: int = 0


def _strip_fence(text: str) -> str:
    stripped = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    return match.group(1) if match else stripped


def _items[T: BaseModel](
    raw: Any, model: type[T], maximum: int, out: ParsedAssessment, name: str
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


def _points(raw: Any, out: ParsedAssessment, name: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise InvalidOutputError("invalid-output", f"'{name}' is not a list.")
    kept: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip() or len(item.strip()) > POINT_MAX:
            out.malformed += 1
        elif len(kept) == MAX_POINTS:
            out.over_limit += 1
        else:
            kept.append(item.strip())
    return kept


def parse(text: str) -> ParsedAssessment:
    """Read the answer. Raises ``InvalidOutputError`` if it is unusable as a whole."""
    try:
        data = json.loads(_strip_fence(text))
    except (json.JSONDecodeError, RecursionError):
        raise InvalidOutputError("invalid-output", "The answer was not valid JSON.") from None
    if not isinstance(data, dict):
        raise InvalidOutputError("invalid-output", "The answer was not a JSON object.")
    out = ParsedAssessment()
    out.unexpected_fields = sum(1 for key in data if key not in KNOWN_KEYS)
    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip() or len(summary.strip()) > SUMMARY_MAX:
        raise InvalidOutputError("invalid-output", "The answer had no usable summary.")
    out.summary = summary.strip()
    uncertainty = data.get("uncertainty")
    if uncertainty not in ASSESSMENT_UNCERTAINTIES:
        raise InvalidOutputError("invalid-output", "The answer had no known uncertainty category.")
    out.uncertainty = str(uncertainty)
    out.precedents = _items(
        data.get("precedents"), ModelCitation, MAX_PRECEDENTS, out, "precedents"
    )
    out.reasoning = _items(data.get("reasoning"), ModelStep, MAX_STEPS, out, "reasoning")
    out.missing_evidence = _points(data.get("missing_evidence"), out, "missing_evidence")
    out.limitations = _points(data.get("limitations"), out, "limitations")
    return out


def _string(max_length: int) -> dict[str, Any]:
    return {"type": "string", "description": f"At most {max_length} characters."}


RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": _string(SUMMARY_MAX),
        "uncertainty": {"type": "string", "enum": list(ASSESSMENT_UNCERTAINTIES)},
        "precedents": {
            "type": "array",
            "description": f"At most {MAX_PRECEDENTS}.",
            "items": {
                "type": "object",
                "properties": {
                    "precedent": {"type": "string", "description": "One given id, e.g. P1."},
                    "stance": {
                        "type": "string",
                        "enum": ["supports", "cuts_against", "does_not_resolve"],
                    },
                    "quote": {
                        "type": "string",
                        "description": "Copied exactly from that precedent's passage.",
                    },
                    "explanation": _string(TEXT_MAX),
                },
                "required": ["precedent", "stance", "quote", "explanation"],
            },
        },
        "reasoning": {
            "type": "array",
            "description": f"At most {MAX_STEPS} steps.",
            "items": {
                "type": "object",
                "properties": {
                    "text": _string(TEXT_MAX),
                    "findings": {"type": "array", "items": {"type": "string"}},
                    "precedents": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "findings", "precedents"],
            },
        },
        "missing_evidence": {"type": "array", "items": _string(POINT_MAX)},
        "limitations": {"type": "array", "items": _string(POINT_MAX)},
    },
    "required": [
        "summary",
        "uncertainty",
        "precedents",
        "reasoning",
        "missing_evidence",
        "limitations",
    ],
}


def schema_sha256() -> str:
    canonical = json.dumps(RESPONSE_SCHEMA, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
