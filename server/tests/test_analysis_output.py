"""Reading the model's answer (Phase 5): untrusted input, parsed defensively."""

from __future__ import annotations

import json

import pytest

from lexflow.analysis.output import RESPONSE_SCHEMA, InvalidOutputError, parse

FACT = {"id": "F1", "statement": "The lease began in 2019.", "evidence": "D1", "quote": "x" * 20}


def answer(**parts: object) -> str:
    base: dict[str, object] = {
        "facts": [],
        "issues": [],
        "precedents": [],
        "contradictions": [],
        "insufficient_evidence": False,
    }
    return json.dumps({**base, **parts})


@pytest.mark.parametrize(
    "text",
    ["", "not json", "[1, 2]", '"facts"', '{"facts": {"id": 1}}', '{"facts": [], '],
)
def test_unusable_answers_are_rejected_as_a_whole(text: str) -> None:
    with pytest.raises(InvalidOutputError) as caught:
        parse(text)
    assert caught.value.code == "invalid-output"


def test_insufficient_flag_must_be_boolean() -> None:
    with pytest.raises(InvalidOutputError):
        parse(answer(insufficient_evidence="yes"))


def test_a_valid_answer_is_read() -> None:
    parsed = parse(answer(facts=[FACT], issues=[{"question": "Q?", "fact_ids": ["F1"]}]))
    assert [f.id for f in parsed.facts] == ["F1"]
    assert parsed.issues[0].fact_ids == ["F1"]
    assert parsed.malformed == 0 and not parsed.outcome_discarded


def test_a_markdown_fence_around_json_is_tolerated() -> None:
    assert len(parse("```json\n" + answer(facts=[FACT]) + "\n```").facts) == 1


def test_malformed_items_are_dropped_and_counted_not_fatal() -> None:
    bad = [
        {"id": "F2", "statement": "no evidence", "quote": "y" * 20},  # missing field
        {**FACT, "id": "fact-3"},  # bad id
        {**FACT, "id": "F4", "statement": "s" * 601},  # too long
        "a string, not an object",
    ]
    parsed = parse(answer(facts=[FACT, *bad]))
    assert [f.id for f in parsed.facts] == ["F1"]
    assert parsed.malformed == 4


def test_items_beyond_the_maximum_are_counted() -> None:
    facts = [{**FACT, "id": f"F{i}"} for i in range(1, 46)]
    parsed = parse(answer(facts=facts))
    assert len(parsed.facts) == 40 and parsed.over_limit == 5


@pytest.mark.parametrize("key", ["outcome_assessment", "outcomeAssessment", "prediction"])
def test_an_outcome_assessment_is_noted_for_discarding(key: str) -> None:
    parsed = parse(json.dumps({key: {"likely": "win"}, "facts": [FACT]}))
    assert parsed.outcome_discarded and len(parsed.facts) == 1


def test_extra_keys_inside_items_are_ignored() -> None:
    parsed = parse(answer(facts=[{**FACT, "citation": "AIR 1999 SC 1", "confidence": 0.9}]))
    assert len(parsed.facts) == 1 and not hasattr(parsed.facts[0], "citation")


def test_the_response_schema_is_plain_json_schema() -> None:
    text = json.dumps(RESPONSE_SCHEMA)
    assert "$ref" not in text and "$defs" not in text and "maxLength" not in text
    assert set(RESPONSE_SCHEMA["required"]) == {
        "facts",
        "issues",
        "precedents",
        "contradictions",
        "insufficient_evidence",
    }
    assert "outcome" not in text
