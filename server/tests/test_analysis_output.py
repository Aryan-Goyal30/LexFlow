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


@pytest.mark.parametrize(
    "key", ["outcome_assessment", "outcomeAssessment", "outcome", "prediction"]
)
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


def test_every_outcome_key_is_covered() -> None:
    from lexflow.analysis.output import OUTCOME_KEYS

    assert {"outcome_assessment", "outcomeAssessment", "outcome", "prediction"} == OUTCOME_KEYS


# The fingerprint of case-analysis-schema-2. If this test fails, the provider
# schema changed: give it a new RESPONSE_SCHEMA_VERSION (and record why) rather
# than editing the expected value alone, so stored runs keep an honest label.
SCHEMA_2_SHA256 = "2b283e9b5b8a33f0cd3babe354fb10878548c2a7f1063733412dea7f2b223a86"


def test_the_schema_version_names_exactly_this_schema() -> None:
    from lexflow.analysis.output import RESPONSE_SCHEMA_VERSION, schema_sha256

    assert RESPONSE_SCHEMA_VERSION == "case-analysis-schema-2"
    assert schema_sha256() == SCHEMA_2_SHA256


ARRAY_SIZE_KEYWORDS = {"minItems", "maxItems", "uniqueItems", "minContains", "maxContains"}


def schema_nodes(node: object, path: str = "$") -> list[tuple[str, dict[str, object]]]:
    found: list[tuple[str, dict[str, object]]] = []
    if isinstance(node, dict):
        found.append((path, node))
        for key, value in node.items():
            found += schema_nodes(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            found += schema_nodes(value, f"{path}[{i}]")
    return found


def test_the_provider_schema_has_no_array_size_keywords_but_states_the_limits() -> None:
    nodes = schema_nodes(RESPONSE_SCHEMA)
    # Not a keyword anywhere in the schema (not even as a nested property name).
    assert [(p, k) for p, n in nodes for k in n if k in ARRAY_SIZE_KEYWORDS] == []
    # Every array still declares its items and says, in words, how many it may have.
    arrays = [(p, n) for p, n in nodes if n.get("type") == "array"]
    assert len(arrays) == 8
    for path, array in arrays:
        assert isinstance(array.get("items"), dict), path
        assert "At most" in str(array.get("description")) or "Two to four" in str(
            array.get("description")
        ), path
    props = RESPONSE_SCHEMA["properties"]
    assert props["facts"]["description"] == "At most 40 facts."
    assert props["issues"]["description"] == "At most 20 issues."
    assert props["precedents"]["description"] == "At most 20 precedents."
    assert props["contradictions"]["description"] == "At most 15 contradictions."
    sources = props["contradictions"]["items"]["properties"]["sources"]
    assert sources["description"] == "Two to four sources."


def test_the_rest_of_the_provider_schema_is_unchanged() -> None:
    props = RESPONSE_SCHEMA["properties"]
    assert RESPONSE_SCHEMA["type"] == "object"
    assert {k: v["type"] for k, v in props.items()} == {
        "facts": "array",
        "issues": "array",
        "precedents": "array",
        "contradictions": "array",
        "insufficient_evidence": "boolean",
    }
    required = {
        name: sorted(props[name]["items"]["required"])
        for name in ("facts", "issues", "precedents", "contradictions")
    }
    assert required == {
        "facts": ["evidence", "id", "quote", "statement"],
        "issues": ["fact_ids", "question"],
        "precedents": ["differences", "evidence", "similarities", "summary"],
        "contradictions": ["description", "sources"],
    }
    source_items = props["contradictions"]["items"]["properties"]["sources"]["items"]
    assert sorted(source_items["required"]) == ["evidence", "quote"]
    assert props["issues"]["items"]["properties"]["fact_ids"]["items"]["type"] == "string"


QUOTE = "q" * 20
SOURCE = {"evidence": "D1", "quote": QUOTE}


def precedent(**changes: object) -> dict[str, object]:
    return {
        "evidence": "J1",
        "summary": "s",
        "similarities": ["a"],
        "differences": ["b"],
        **changes,
    }


def test_list_limits_are_still_enforced_by_the_parser() -> None:
    parsed = parse(
        answer(
            facts=[{**FACT, "id": f"F{i}"} for i in range(1, 42)],
            issues=[{"question": "Q?", "fact_ids": ["F1"]}] * 21,
            precedents=[precedent()] * 21,
            contradictions=[{"description": "d", "sources": [SOURCE, SOURCE]}] * 16,
        )
    )
    assert (len(parsed.facts), len(parsed.issues)) == (40, 20)
    assert (len(parsed.precedents), len(parsed.contradictions)) == (20, 15)
    assert parsed.over_limit == 4 and parsed.malformed == 0


def test_item_limits_are_still_enforced_by_the_parser() -> None:
    def kept(**parts: object) -> tuple[int, int]:
        parsed = parse(answer(**parts))
        counts = (
            len(parsed.issues) + len(parsed.precedents) + len(parsed.contradictions),
            parsed.malformed,
        )
        return counts

    # Five similarities or differences, twenty fact ids and two to four sources fit ...
    assert kept(precedents=[precedent(similarities=list("abcde"))]) == (1, 0)
    assert kept(precedents=[precedent(differences=list("abcde"))]) == (1, 0)
    assert kept(issues=[{"question": "Q?", "fact_ids": ["F1"] * 20}]) == (1, 0)
    for n in (2, 3, 4):
        assert kept(contradictions=[{"description": "d", "sources": [SOURCE] * n}]) == (1, 0)
    # ... and one more (or fewer) makes the item malformed, which drops and counts it.
    assert kept(precedents=[precedent(similarities=list("abcdef"))]) == (0, 1)
    assert kept(precedents=[precedent(differences=list("abcdef"))]) == (0, 1)
    assert kept(issues=[{"question": "Q?", "fact_ids": ["F1"] * 21}]) == (0, 1)
    for n in (0, 1, 5):
        assert kept(contradictions=[{"description": "d", "sources": [SOURCE] * n}]) == (0, 1)
