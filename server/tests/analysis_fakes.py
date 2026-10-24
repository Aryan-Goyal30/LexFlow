"""Synthetic evidence and fake Gemini responses for the analysis tests.

Nothing here contacts a provider: ``FakeGeminiClient`` stands in for
``google.genai.Client`` and records what it was asked.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from lexflow.analysis.evidence import CaseContext, Evidence, JudgmentPassage, Passage

DOC_A = uuid.UUID("00000000-0000-4000-8000-0000000000a1")
DOC_B = uuid.UUID("00000000-0000-4000-8000-0000000000b2")
JUDGMENT = uuid.UUID("00000000-0000-4000-8000-0000000000c3")

TEXT_A = (
    "SYNTHETIC. The tenancy agreement dated 1 April 2019 fixed the monthly rent at "
    "Rs. 40,000, payable on the fifth day of each month."
)
TEXT_B = (
    "SYNTHETIC. The landlord's notice of 3 March 2024 states that the monthly rent "
    "was Rs. 45,000 and that three months were unpaid."
)
TEXT_J = (
    "SYNTHETIC. Where the rent stated in a notice differs from the rent in the written "
    "agreement, the agreement governs unless it was varied in writing."
)


def passage(n: int, document: uuid.UUID, text: str, *, page: int | None = 1) -> Passage:
    return Passage(
        id=f"D{n}",
        document_id=document,
        document_name=f"Synthetic {n}.pdf",
        chunk_id=uuid.uuid5(document, str(n)),
        chunk_number=n,
        section_number=page or 1,
        page_number=page,
        text=text,
        content_sha256=f"{n:064x}",
    )


def judgment_passage(
    n: int = 1, *, citation: str | None = "(SYN) 2019 TEST 101"
) -> JudgmentPassage:
    return JudgmentPassage(
        id=f"J{n}",
        judgment_id=JUDGMENT,
        title="Asha Rao v. Bharat Traders (SYNTHETIC)",
        court="SYNTHETIC District Court (test fixture)",
        citation=citation,
        year=2019,
        synthetic=True,
        rank=n,
        chunk_id=uuid.uuid5(JUDGMENT, str(n)),
        section_number=2,
        page_number=2,
        text=TEXT_J,
        content_sha256=f"{n + 100:064x}",
    )


def evidence(*, judgments: bool = True, passages: bool = True) -> Evidence:
    context = CaseContext(
        case_number="LF-2026-0001",
        title="SYNTHETIC rent dispute",
        practice_area="Civil",
        status="Open",
        court_name=None,
        opposing_party=None,
        description="SYNTHETIC: a dispute about the agreed rent.",
        timeline=[],
    )
    return Evidence(
        context=context,
        passages=[passage(1, DOC_A, TEXT_A), passage(2, DOC_B, TEXT_B, page=None)]
        if passages
        else [],
        judgments=[judgment_passage()] if judgments else [],
        documents_selected=2,
    )


# The SYNTHETIC document of the live smoke test (M8e, run 4fc9ab87), byte for
# byte as uploaded (recovered from the session transcript, M10.1). Line endings
# are normalised so a CRLF checkout gives the same bytes.
SMOKE_NOTICE = Path(__file__).parent / "fixtures" / "analysis" / "SYNTHETIC-phase5-smoke-notice.txt"
SMOKE_NOTICE_SHA256 = "a7ff616286426b3f45319c4690b1c76711e6558563c5dda1c99ecbe6d49ce628"
SMOKE_DOC = uuid.UUID("00000000-0000-4000-8000-0000000005e0")


def smoke_notice_bytes() -> bytes:
    return SMOKE_NOTICE.read_bytes().replace(b"\r\n", b"\n")


def smoke_evidence() -> Evidence:
    """D1 and D2 exactly as the live run received them: the real extraction and
    chunking code with the default chunk size (1200) and overlap (200)."""
    from lexflow.extraction import Limits, extract
    from lexflow.extraction.chunking import chunk_sections

    data = smoke_notice_bytes()
    assert hashlib.sha256(data).hexdigest() == SMOKE_NOTICE_SHA256
    sections = extract("text/plain", data, Limits(100, 1_000_000, 10_000_000)).sections
    passages = [
        Passage(
            id=f"D{n}",
            document_id=SMOKE_DOC,
            document_name="SYNTHETIC-phase5-smoke-notice.txt",
            chunk_id=uuid.uuid5(SMOKE_DOC, str(n)),
            chunk_number=n,
            section_number=chunk.section_number,
            page_number=chunk.page_number,
            text=chunk.text,
            content_sha256=chunk.content_sha256,
        )
        for n, chunk in enumerate(chunk_sections(sections, 1200, 200), start=1)
    ]
    context = CaseContext(
        case_number="LF-2026-0361",
        title="SYNTHETIC smoke-test case",
        practice_area="Intellectual Property",
        status="Open",
        court_name=None,
        opposing_party=None,
        description="SYNTHETIC: a trade-mark dispute with planted traps.",
        timeline=[],
    )
    return Evidence(context=context, passages=passages, judgments=[], documents_selected=1)


def candidate(text: str, *, finish: str = "STOP", thought: str | None = None) -> Any:
    parts = []
    if thought is not None:
        parts.append(SimpleNamespace(text=thought, thought=True))
    parts.append(SimpleNamespace(text=text, thought=None))
    return SimpleNamespace(
        content=SimpleNamespace(parts=parts), finish_reason=SimpleNamespace(name=finish)
    )


def response(
    text: str = "{}",
    *,
    finish: str = "STOP",
    block: str | None = None,
    candidates: list[Any] | None = None,
    thought: str | None = None,
) -> Any:
    return SimpleNamespace(
        prompt_feedback=SimpleNamespace(block_reason=block) if block else None,
        candidates=[candidate(text, finish=finish, thought=thought)]
        if candidates is None
        else candidates,
        usage_metadata=SimpleNamespace(
            prompt_token_count=1200,
            candidates_token_count=300,
            thoughts_token_count=50,
            total_token_count=1550,
        ),
    )


@dataclass
class FakeGeminiClient:
    """Answers (or raises) from a script, one item per call, and records calls."""

    script: list[Any]
    calls: list[dict[str, Any]] = field(default_factory=list)

    @property
    def models(self) -> FakeGeminiClient:
        return self

    def generate_content(self, *, model: str, contents: Any, config: Any) -> Any:
        self.calls.append({"model": model, "contents": contents, "config": config})
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


@dataclass
class Factory:
    client: FakeGeminiClient
    built: list[tuple[str, int]] = field(default_factory=list)

    def __call__(self, api_key: str, timeout_ms: int) -> FakeGeminiClient:
        self.built.append((api_key, timeout_ms))
        return self.client


def today() -> date:
    return date(2026, 10, 20)


@dataclass
class ScriptedAnswers:
    """A provider that returns (or raises) prepared answers in order."""

    answers: list[Any]
    # Runs in the tests are confirmed for the scripted provider; the worker
    # refuses a run whose provider differs from its own.
    name: str = "scripted"
    model: str = "fake-model-for-tests"
    requests: list[Any] = field(default_factory=list)

    def generate(self, request: Any) -> Any:
        from lexflow.analysis.provider import Response

        self.requests.append(request)
        item = self.answers.pop(0)
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, Response):
            return item
        return Response(text=item, usage={"totalTokens": 10})
