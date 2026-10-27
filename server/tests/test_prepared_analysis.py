"""The prepared demonstration provider (not AI) for the FICTIONAL Aarav Foods matter.

Its findings must survive the same validation as a model's: every quoted sentence
must be in the text LexFlow extracts from the uploaded documents, and every
precedent must rest on a judgment passage in the evidence. It answers only for
its own case, and only it (a local provider) is exempt from the D1 rule that
keeps client material away from external AI services.
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
import uuid
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from lexflow.analysis import runs
from lexflow.analysis.evidence import JudgmentPassage, assemble
from lexflow.analysis.prepared import PreparedProvider, pinned_judgments, script_for
from lexflow.analysis.provider import client_data_allowed
from lexflow.config import Settings
from lexflow.extraction import DOCX, PDF, extract
from lexflow.extraction import Limits as ExtractionLimits
from lexflow.models import Case, JudgmentChunk
from tests.access_fixtures import SATTVIK
from tests.embedding_fakes import make_ready
from tests.test_analysis_evidence import WIDE, collection  # noqa: F401 - fixture

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "make_aarav_demo_pack.py"
TITLE = "Aarav Foods Pvt. Ltd. v. Sunrise Retail Pvt. Ltd. (Fictional)"
LIMITS = ExtractionLimits(max_pages=100, max_text_bytes=1_000_000, max_unpacked_bytes=10_000_000)

# Passages of the genuine Supreme Court judgments the comparisons rest on, as stored
# in the verified corpus (whitespace tidied). The corpus itself stays outside Git.
JUDGMENTS = {
    "Amritdhara Pharmacy v. Satyadeo Gupta": "has to be approached from the point of view of "
    "a man of average intelligence and imperfect recollection. To such a man the overall "
    "structural and phonetic similarity of the two names is likely to deceive",
    "Parle Products (P) Ltd. v. J. P. & Co., Mysore": "the broad and essential features of "
    "the two are to be considered. They should not be placed side by side to find out if "
    "there are any differences in the design and if so, whether they are of such character",
    "M/s. Nandhini Deluxe v. M/s. Karnataka Co-operative Milk Producers Federation Ltd.": "that "
    "the proprietor of a trade mark cannot enjoy monopoly over the entire class of goods and, "
    "particularly, when he is not using the said trade mark in respect of certain goods",
    "Pernod Ricard India Private Limited & Another v. Karanveer Singh Chhabra": "The exercise "
    "at that stage is limited to determining whether a prima facie case exists, along with "
    "considerations of balance of convenience and potential irreparable injury. The focus is "
    "not to adjudicate the ultimate rights of the parties.",
    "Indian Performing Rights Society Ltd. v. Sanjay Dalia & Anr.": "would be the relevant "
    "place for the filing of a suit and not the principal place of business.",
}


def _pack() -> ModuleType:
    spec = importlib.util.spec_from_file_location("make_aarav_demo_pack", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _documents() -> dict[str, list[str]]:
    """Each document's sections, as LexFlow extracts them."""
    texts = {}
    for name, build in _pack().DOCUMENTS:
        kind = PDF if name.endswith(".pdf") else DOCX
        texts[name] = [s.text for s in extract(kind, build(), LIMITS).sections]
    return texts


def _normal(text: str) -> str:
    return re.sub(r"\s+", " ", text).replace("\u2019", "'").strip()


def test_every_prepared_quote_is_in_the_text_lexflow_extracts() -> None:
    script = script_for(TITLE)
    assert script is not None
    documents = {name: _normal(" ".join(parts)) for name, parts in _documents().items()}
    quoted = [*script["facts"], *(s for c in script["contradictions"] for s in c["sources"])]
    for item in quoted:
        assert _normal(item["quote"]) in documents[item["document"]], item["quote"]
    for name, text in documents.items():
        assert "ILLUSTRATIVE ACADEMIC MATERIAL - FICTIONAL" in text, name


def test_the_prepared_analysis_passes_validation_with_nothing_removed(
    db: Session, people: Any
) -> None:
    case = db.get(Case, SATTVIK)
    assert case is not None
    case.title = TITLE  # the fictional matter, as registered in the application
    ids = [make_ready(db, SATTVIK, name, pages) for name, pages in _documents().items()]
    db.commit()
    evidence = assemble(db, case, ids, WIDE)
    evidence.judgments = [
        JudgmentPassage(
            id=f"J{rank}",
            judgment_id=uuid.uuid4(),
            title=title,
            court="Supreme Court of India",
            citation=None,
            year=None,
            synthetic=False,
            rank=rank,
            chunk_id=uuid.uuid4(),
            section_number=1,
            page_number=1,
            text=text,
            content_sha256=hashlib.sha256(text.encode()).hexdigest(),
        )
        for rank, (title, text) in enumerate(JUDGMENTS.items(), start=1)
    ]
    outcome = runs.check_answer(PreparedProvider(), evidence, 8_000, label="prepared")
    assert isinstance(outcome, runs.Ready), outcome
    result = outcome.result
    assert result.removed.count == 0, result.removed
    assert (len(result.facts), len(result.issues)) == (17, 8)
    assert len(result.precedents) == 5 and not any(p.synthetic for p in result.precedents)
    assert len(result.contradictions) == 2
    assert outcome.provider == "prepared"


def test_other_cases_get_no_prepared_findings(db: Session, people: Any) -> None:
    case = db.get(Case, SATTVIK)
    assert case is not None
    evidence = assemble(db, case, [], WIDE)
    outcome = runs.check_answer(PreparedProvider(), evidence, 8_000, label="other")
    assert isinstance(outcome, runs.Ready)
    assert outcome.result.facts == [] and outcome.result.insufficient_evidence


def test_only_the_local_prepared_provider_is_exempt_from_the_sample_case_rule() -> None:
    def settings(provider: str, allow: bool) -> Settings:
        values: dict[str, Any] = {
            "LEXFLOW_AI_PROVIDER": provider,
            "LEXFLOW_AI_ALLOW_CLIENT_DATA": allow,
            "GEMINI_API_KEY": "AIzaFAKE-not-real",
            "GEMINI_MODEL": "gemini-test",
        }
        return Settings(**values)

    assert client_data_allowed(settings("prepared", False))
    assert not client_data_allowed(settings("gemini", False)), "external: D1 still applies"
    assert not client_data_allowed(settings("scripted", False))
    assert client_data_allowed(settings("gemini", True)), "only by explicit configuration"


def test_pinned_judgment_passages_are_added_to_the_evidence(
    db: Session,
    people: Any,
    collection: None,  # noqa: F811
) -> None:
    case = db.get(Case, SATTVIK)
    assert case is not None
    chunk = db.scalars(select(JudgmentChunk).order_by(JudgmentChunk.id)).first()
    assert chunk is not None
    words = " ".join(chunk.text.split()[5:15])
    from lexflow.models import Judgment

    judgment = db.get(Judgment, chunk.judgment_id)
    assert judgment is not None
    limits = replace(WIDE, max_precedents=0, pinned=((judgment.title[:12], words),))
    evidence = assemble(db, case, [], limits)
    assert [p.chunk_id for p in evidence.judgments] == [chunk.id]
    assert evidence.judgments[0].id == "J1"
    assert pinned_judgments(TITLE)[0][0] == "Amritdhara Pharmacy"


def test_an_approved_case_may_go_to_gemini_and_no_other() -> None:
    approved = uuid.uuid4()
    values: dict[str, Any] = {
        "LEXFLOW_AI_PROVIDER": "gemini",
        "LEXFLOW_AI_ALLOW_CLIENT_DATA": False,
        "LEXFLOW_AI_APPROVED_CASE_IDS": [str(approved)],
        "GEMINI_API_KEY": "AIzaFAKE-not-real",
        "GEMINI_MODEL": "gemini-test",
    }
    settings = Settings(**values)
    assert client_data_allowed(settings, approved)
    assert not client_data_allowed(settings, uuid.uuid4()), "D1 still applies to every other case"
    assert not client_data_allowed(settings), "no case given: no exemption"


LIVE_LIKE = "postgresql+psycopg://user:secret@127.0.0.1:5432/lexflow"


def test_gemini_assessment_only_for_owner_approved_cases() -> None:
    from lexflow.assessment import provider as assessment_provider
    from lexflow.assessment.inputs import Inputs

    approved = uuid.uuid4()
    base: dict[str, Any] = {
        "DATABASE_URL": LIVE_LIKE,
        "LEXFLOW_AI_PROVIDER": "gemini",
        "GEMINI_API_KEY": "AIzaFAKE-not-real",
        "GEMINI_MODEL": "gemini-test",
        "LEXFLOW_OUTCOME_ASSESSMENT": True,
    }
    with pytest.raises(ValueError, match="synthetic-only demo"):
        Settings(**base)  # no approved case: still refused outside test databases
    settings = Settings(**base, LEXFLOW_AI_APPROVED_CASE_IDS=[str(approved)])
    provider = assessment_provider.provider_for(settings)
    assert isinstance(provider, assessment_provider.GeminiAssessmentProvider)
    assert assessment_provider.PROVIDER_LABELS["gemini"] == "Google Gemini API (AI)"
    assert assessment_provider.allowed_for(settings, approved)
    assert not assessment_provider.allowed_for(settings, uuid.uuid4())
    genuine = Inputs(findings=[object()], precedents=[type("P", (), {"synthetic": False})()])  # type: ignore[list-item]
    assert genuine.gate() == "genuine-precedents", "unapproved: genuine judgments refused"
    assert genuine.gate(allow_genuine=True) is None
