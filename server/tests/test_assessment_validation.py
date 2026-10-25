"""Outcome assessment (Phase 7 demo): the contract and the strict validation.

Adversarial answers are built by hand against SYNTHETIC inputs; no database,
no provider. Each test names the rule it holds (docs/PHASE7_PLAN.md, D7-5).
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest

from lexflow.analysis.output import InvalidOutputError
from lexflow.assessment import output, prompt, validation
from lexflow.assessment.inputs import InputFinding, InputPrecedent, Inputs
from lexflow.assessment.provider import AssessmentRequest
from lexflow.assessment.scripted import ScriptedAssessmentProvider

PASSAGE_1 = (
    "SYNTHETIC: Prior continuous use of a mark since 2012 outweighs a later registration where "
    "the registrant knew of the earlier user and adopted the mark dishonestly."
)
PASSAGE_2 = (
    "SYNTHETIC: Where the earlier user abandoned the mark for several years, the later "
    "registered proprietor is protected and the earlier use does not defeat the registration."
)
QUOTE_1 = "Prior continuous use of a mark since 2012 outweighs a later registration"
QUOTE_2 = "the later registered proprietor is protected"


def precedent(ref: str, text: str, *, synthetic: bool = True) -> InputPrecedent:
    return InputPrecedent(
        id=ref,
        summary=f"SYNTHETIC comparison {ref}",
        edited=False,
        review_version=1,
        judgment_id=uuid.uuid4(),
        title=f"Meera Textiles v. Kiran Mills ({ref}, SYNTHETIC)",
        court="SYNTHETIC High Court (test fixture)",
        citation=f"(SYN) 2020 TEST {ref[1:]}",
        year=2020,
        synthetic=synthetic,
        chunk_id=uuid.uuid4(),
        section_number=2,
        page_number=2,
        text=text,
        content_sha256="0" * 64,
    )


def make_inputs(*, two: bool = True, synthetic: bool = True) -> Inputs:
    inputs = Inputs(
        findings=[
            InputFinding("fact", "F1", "SYNTHETIC: the mark was registered in 2015.", False, 1),
            InputFinding("fact", "F2", "SYNTHETIC: first use was in 2012.", True, 2),
            InputFinding("issue", "I1", "SYNTHETIC: which first-use date is right?", False, 1),
        ],
        precedents=[precedent("P1", PASSAGE_1, synthetic=synthetic)],
        excluded={"rejected": 1, "unreviewed": 2},
    )
    if two:
        inputs.precedents.append(precedent("P2", PASSAGE_2, synthetic=synthetic))
    return inputs


def answer(**overrides: Any) -> str:
    base: dict[str, Any] = {
        "summary": "The accepted facts are compared with two retrieved passages.",
        "uncertainty": "mixed_evidence",
        "precedents": [
            {
                "precedent": "P1",
                "stance": "supports",
                "quote": QUOTE_1,
                "explanation": "Prior use is weighed against registration in P1.",
            },
            {
                "precedent": "P2",
                "stance": "cuts_against",
                "quote": QUOTE_2,
                "explanation": "P2 protects a registered proprietor after abandonment.",
            },
        ],
        "reasoning": [
            {"text": "F2 records earlier use, as in P1.", "findings": ["F2"], "precedents": ["P1"]},
            {"text": "Abandonment is not in the facts.", "findings": ["F1"], "precedents": ["P2"]},
        ],
        "missing_evidence": ["Whether use was continuous after 2012."],
        "limitations": ["Only two passages were compared."],
    }
    base.update(overrides)
    return json.dumps(base)


def check(text: str, inputs: Inputs | None = None, *, scripted: bool = False) -> validation.Verdict:
    return validation.validate(output.parse(text), inputs or make_inputs(), scripted=scripted)


def codes(verdict: validation.Verdict) -> dict[str, int]:
    return {r.code: r.count for r in verdict.removed.reasons}


# --- the contract ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[]",
        json.dumps({"uncertainty": "mixed_evidence"}),  # no summary
        json.dumps({"summary": " ", "uncertainty": "mixed_evidence"}),
        json.dumps({"summary": "ok", "uncertainty": "70%"}),  # not a category
        json.dumps({"summary": "ok", "uncertainty": "mixed_evidence", "precedents": {}}),
    ],
)
def test_an_unusable_answer_is_invalid_output(text: str) -> None:
    with pytest.raises(InvalidOutputError):
        output.parse(text)


def test_a_valid_answer_is_ready_with_server_labels() -> None:
    verdict = check(answer())
    assert verdict.status == "ready" and verdict.result is not None
    result = verdict.result
    assert result.label == "decision-support"
    assert result.uncertainty == "mixed_evidence"
    assert [(p.ref, p.stance) for p in result.precedents] == [
        ("P1", "supports"),
        ("P2", "cuts_against"),
    ]
    # Title, court, citation and the synthetic flag come from the inputs, not the answer.
    assert all(p.synthetic and p.title.endswith("SYNTHETIC)") for p in result.precedents)
    assert result.all_precedents_synthetic and result.demo_only
    assert [s.id for s in result.reasoning] == ["R1", "R2"]
    assert verdict.removed.count == 0


def test_a_score_or_relabelling_field_is_discarded_and_counted() -> None:
    verdict = check(answer(probability=0.7, win_chance="70%", synthetic=False))
    assert verdict.status == "ready" and verdict.result is not None
    assert codes(verdict) == {"unexpected-field": 3}
    dumped = verdict.result.model_dump_json()
    assert "0.7" not in dumped and "70%" not in dumped
    assert all(p.synthetic for p in verdict.result.precedents)


# --- precedents --------------------------------------------------------------------------


def test_an_invented_or_unaccepted_precedent_is_removed() -> None:
    cited = [
        {"precedent": "P1", "stance": "supports", "quote": QUOTE_1, "explanation": "Fits F2."},
        {"precedent": "P9", "stance": "supports", "quote": QUOTE_1, "explanation": "Invented."},
        {"precedent": "J1", "stance": "supports", "quote": QUOTE_1, "explanation": "Not a P id."},
    ]
    steps = [{"text": "F2 and P1.", "findings": ["F2"], "precedents": ["P1"]}]
    verdict = check(answer(precedents=cited, reasoning=steps), make_inputs(two=False))
    assert verdict.result is not None
    assert [p.ref for p in verdict.result.precedents] == ["P1"]
    assert codes(verdict)["unknown-precedent"] == 2


@pytest.mark.parametrize(
    ("quote", "code"),
    [
        ("Prior use always defeats any registration whatsoever", "quote-not-found"),
        ("Prior use", "quote-too-short"),
        # Moved to the other precedent's passage: never accepted for P1.
        (QUOTE_2, "quote-not-found"),
    ],
)
def test_an_unverifiable_quote_removes_the_precedent(quote: str, code: str) -> None:
    cited = [
        {"precedent": "P1", "stance": "supports", "quote": quote, "explanation": "Fits."},
        {"precedent": "P2", "stance": "cuts_against", "quote": QUOTE_2, "explanation": "No."},
    ]
    verdict = check(answer(precedents=cited))
    assert verdict.result is not None
    assert [p.ref for p in verdict.result.precedents] == ["P2"]
    assert codes(verdict)[code] == 1
    # The step resting on P1 lost its support with it.
    assert codes(verdict)["unsupported-step"] == 1


def test_a_shortened_quote_verifies_piece_by_piece() -> None:
    cited = [
        {
            "precedent": "P1",
            "stance": "supports",
            "quote": "Prior continuous use of a mark ... adopted the mark dishonestly",
            "explanation": "Fits.",
        }
    ]
    steps = [{"text": "F2 and P1.", "findings": ["F2"], "precedents": ["P1"]}]
    verdict = check(answer(precedents=cited, reasoning=steps, uncertainty="limited_support"))
    assert verdict.result is not None
    assert verdict.result.precedents[0].quote.count("…") == 1


def test_a_repeated_precedent_counts_once() -> None:
    first = {"precedent": "P1", "stance": "supports", "quote": QUOTE_1, "explanation": "Fits."}
    steps = [{"text": "F2 and P1.", "findings": ["F2"], "precedents": ["P1"]}]
    verdict = check(answer(precedents=[first, first], reasoning=steps))
    assert codes(verdict)["duplicate"] == 1


def test_no_verified_precedent_means_no_assessment() -> None:
    cited = [
        {
            "precedent": "P1",
            "stance": "supports",
            "quote": "Not in it at all, anywhere.",
            "explanation": "Fits.",
        }
    ]
    verdict = check(answer(precedents=cited))
    assert (verdict.status, verdict.reason_code, verdict.result) == (
        "insufficient",
        "no-verified-precedent",
        None,
    )


# --- reasoning ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "step",
    [
        {"text": "Rests on nothing.", "findings": [], "precedents": []},
        {"text": "Rests on a rejected finding.", "findings": ["F3"], "precedents": []},
        {"text": "Rests on an unreviewed issue.", "findings": ["I2"], "precedents": ["P1"]},
        {"text": "Rests on an uncited precedent.", "findings": ["F1"], "precedents": ["P7"]},
        {"text": "Rests on an evidence id.", "findings": ["D1"], "precedents": []},
    ],
)
def test_an_unsupported_reasoning_step_is_removed(step: dict[str, Any]) -> None:
    good = {"text": "F2 and P1.", "findings": ["F2"], "precedents": ["P1"]}
    verdict = check(answer(reasoning=[good, step]))
    assert verdict.result is not None
    assert len(verdict.result.reasoning) == 1
    assert codes(verdict) == {"unsupported-step": 1}


def test_no_supported_reasoning_means_no_assessment() -> None:
    steps = [{"text": "Rests on nothing.", "findings": [], "precedents": []}]
    verdict = check(answer(reasoning=steps))
    assert (verdict.status, verdict.reason_code) == ("insufficient", "no-supported-reasoning")


# --- forbidden prose -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("summary", "code"),
    [
        ("The plaintiff has a 70% chance of winning.", "probability-language"),
        ("There is a 0.7 probability of success.", "probability-language"),
        ("The odds favour the plaintiff.", "probability-language"),
        ("In 3 out of 4 comparable matters the user won.", "probability-language"),
        ("The chances of winning the suit look good.", "probability-language"),
        ("The suit is likely to succeed.", "outcome-wording"),
        ("The court will hold that prior use prevails.", "outcome-wording"),
        ("The plaintiff will certainly win.", "outcome-wording"),
        ("The defendant is bound to lose.", "outcome-wording"),
        ("This follows AIR 1999 SC 123.", "unverified-citation"),
        ("As held in Sharma v. Verma, prior use prevails.", "unverified-citation"),
        ("P1 is a real, binding precedent on this point.", "synthetic-misrepresented"),
        ("P1 is not fictional and is good law.", "synthetic-misrepresented"),
    ],
)
def test_a_forbidden_summary_withholds_the_whole_assessment(summary: str, code: str) -> None:
    verdict = check(answer(summary=summary))
    assert (verdict.status, verdict.reason_code, verdict.result) == (
        "insufficient",
        "summary-withheld",
        None,
    )
    assert codes(verdict) == {code: 1}


@pytest.mark.parametrize(
    "summary",
    [
        "The reply is at odds with the plaint on the date of first use.",
        "P1 discusses likelihood of confusion between the marks.",
        "The respondent had a fair chance to be heard.",
        "Order 39 in 2017 was cited in the plaint.",
        "P1 is a SYNTHETIC test judgment used for this demonstration.",
    ],
)
def test_ordinary_wording_is_kept(summary: str) -> None:
    verdict = check(answer(summary=summary))
    assert verdict.status == "ready"


def test_forbidden_prose_in_an_item_removes_only_that_item() -> None:
    cited = json.loads(answer())["precedents"]
    cited[1]["explanation"] = "P2 gives the defendant odds of 2 to 1."
    steps = [
        {"text": "F2 and P1.", "findings": ["F2"], "precedents": ["P1"]},
        {"text": "The court will dismiss the suit.", "findings": ["F1"], "precedents": ["P1"]},
    ]
    verdict = check(
        answer(
            precedents=cited,
            reasoning=steps,
            uncertainty="limited_support",
            limitations=["A 60% estimate.", "Only two passages."],
        )
    )
    assert verdict.result is not None
    assert [p.ref for p in verdict.result.precedents] == ["P1"]
    assert len(verdict.result.reasoning) == 1
    assert verdict.result.limitations == ["Only two passages."]
    assert codes(verdict) == {"outcome-wording": 1, "probability-language": 2}


def test_real_precedents_are_not_checked_for_synthetic_wording() -> None:
    verdict = check(answer(summary="P1 is a reported decision."), make_inputs(synthetic=False))
    assert verdict.status == "ready" and verdict.result is not None
    assert not verdict.result.all_precedents_synthetic
    assert not verdict.result.demo_only
    scripted = check(answer(), make_inputs(synthetic=False), scripted=True)
    assert scripted.result is not None and scripted.result.demo_only


# --- the uncertainty category ----------------------------------------------------------


@pytest.mark.parametrize(
    ("stances", "chosen", "kept", "adjusted"),
    [
        (("supports", "cuts_against"), "evidence_supports_position", "mixed_evidence", True),
        (("supports", "cuts_against"), "limited_support", "limited_support", False),
        (("supports", "does_not_resolve"), "mixed_evidence", "limited_support", True),
        (
            ("supports", "supports"),
            "evidence_supports_position",
            "evidence_supports_position",
            False,
        ),
        (("cuts_against", "cuts_against"), "evidence_supports_position", "limited_support", True),
    ],
)
def test_the_category_must_fit_the_cited_stances(
    stances: tuple[str, str], chosen: str, kept: str, adjusted: bool
) -> None:
    cited = json.loads(answer())["precedents"]
    for item, stance in zip(cited, stances, strict=True):
        item["stance"] = stance
    verdict = check(answer(precedents=cited, uncertainty=chosen))
    assert verdict.result is not None
    assert verdict.result.uncertainty == kept
    assert ("uncertainty-adjusted" in codes(verdict)) is adjusted


def test_precedents_that_resolve_nothing_give_no_assessment() -> None:
    cited = json.loads(answer())["precedents"]
    for item in cited:
        item["stance"] = "does_not_resolve"
    verdict = check(answer(precedents=cited, uncertainty="limited_support"))
    assert (verdict.status, verdict.reason_code) == ("insufficient", "assessed-insufficient")


def test_a_cautious_insufficient_basis_is_never_overridden() -> None:
    verdict = check(answer(uncertainty="insufficient_basis"))
    assert (verdict.status, verdict.reason_code) == ("insufficient", "assessed-insufficient")
    assert "uncertainty-adjusted" not in codes(verdict)


# --- the scripted double and the prompt ------------------------------------------------


def request(inputs: Inputs) -> AssessmentRequest:
    return AssessmentRequest(
        system_instruction=prompt.SYSTEM_INSTRUCTION,
        prompt=prompt.render(inputs),
        response_schema=output.RESPONSE_SCHEMA,
        max_output_tokens=1024,
        inputs=inputs,
    )


def test_the_scripted_answer_validates_and_its_planted_errors_are_removed() -> None:
    inputs = make_inputs()
    response = ScriptedAssessmentProvider().generate(request(inputs))
    verdict = check(response.text, inputs, scripted=True)
    assert verdict.status == "ready" and verdict.result is not None
    assert verdict.result.uncertainty == "mixed_evidence"
    assert [p.stance for p in verdict.result.precedents] == ["supports", "cuts_against"]
    assert codes(verdict) == {"unknown-precedent": 1, "unsupported-step": 1}
    assert verdict.result.summary.startswith("[Scripted]")
    assert verdict.result.demo_only


def test_the_prompt_holds_only_accepted_inputs_and_labels_synthetic_judgments() -> None:
    inputs = make_inputs()
    text = prompt.render(inputs)
    assert "SYNTHETIC test judgment: fictional, not real law" in text
    assert "F2 [fact] (lawyer's wording)" in text
    assert PASSAGE_1 in text and PASSAGE_2 in text
    # Only accepted findings are listed; what was left out is not described.
    assert "rejected" not in text and "unreviewed" not in text
    assert "Never give a probability" in prompt.SYSTEM_INSTRUCTION


def test_the_contract_has_no_numeric_field() -> None:
    def types(node: Any) -> set[str]:
        found: set[str] = set()
        if isinstance(node, dict):
            if isinstance(node.get("type"), str):
                found.add(node["type"])
            for value in node.values():
                found |= types(value)
        elif isinstance(node, list):
            for value in node:
                found |= types(value)
        return found

    assert types(output.RESPONSE_SCHEMA) <= {"object", "array", "string"}
