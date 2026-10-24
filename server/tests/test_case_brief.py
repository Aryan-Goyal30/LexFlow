"""The case brief (Phase 6, AC5-AC7): a DOCX with only the findings a lawyer
accepted, with citations, counts, synthetic labels and changed-source flags,
and never a reviewer's note. SYNTHETIC runs only; no provider is called."""

from __future__ import annotations

import io
import json
from collections.abc import Callable
from typing import Any

import docx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lexflow.api import reviews as reviews_api
from lexflow.models import AnalysisRun, AuditEvent, User
from lexflow.services.brief import (
    CHANGED_NOTE,
    DISCLAIMER,
    DOCX_MEDIA_TYPE,
    PASSAGE_CHANGED_NOTE,
    SYNTHETIC_LABEL,
)
from tests.access_fixtures import SATTVIK
from tests.review_fixtures import CHUNK, DOC, JCHUNK, JUDGMENT, ready_run, result
from tests.test_portal import as_client, portal_people  # noqa: F401 - fixtures

As = Callable[[str], TestClient]
NOTE = "SYNTHETIC-PRIVATE-NOTE-5512"
WORDING = "SYNTHETIC: first use is disputed between 2015 and 2017 (lawyer's wording)."


@pytest.fixture
def run(db: Session, people: dict[str, User]) -> AnalysisRun:
    return ready_run(db, SATTVIK, requested_by=people["lead"].id)


def decide(http: TestClient, run: AnalysisRun, finding: str, status: str, **extra: Any) -> None:
    base = f"/api/cases/{SATTVIK}/analysis-runs/{run.id}/reviews/{finding}"
    response = http.put(base, json={"status": status, "expectedVersion": 0, **extra})
    assert response.status_code == 200, response.text


def brief_url(run: AnalysisRun) -> str:
    return f"/api/cases/{SATTVIK}/analysis-runs/{run.id}/brief"


def text_of(content: bytes) -> str:
    document = docx.Document(io.BytesIO(content))
    return "\n".join(p.text for p in document.paragraphs)


@pytest.fixture
def reviewed(as_: As, run: AnalysisRun) -> AnalysisRun:
    lead = as_("lead")
    decide(lead, run, "F1", "accepted", note=NOTE)
    decide(lead, run, "F2", "rejected", note=NOTE)
    decide(lead, run, "C1", "edited", reviewedText=WORDING, note=NOTE)
    decide(lead, run, "P1", "accepted")
    # I1 stays unreviewed.
    return run


def test_the_brief_holds_only_accepted_findings(as_: As, reviewed: AnalysisRun) -> None:
    response = as_("lead").get(brief_url(reviewed))
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == DOCX_MEDIA_TYPE
    assert response.headers["cache-control"] == "no-store"
    text = text_of(response.content)
    original = result()
    assert original["facts"][0]["statement"] in text  # F1 accepted
    assert original["facts"][1]["statement"] not in text  # F2 rejected
    assert original["issues"][0]["question"] not in text  # I1 unreviewed
    assert WORDING in text and "Wording by the reviewing lawyer." in text  # C1 edited
    assert original["contradictions"][0]["description"] not in text  # the AI's version
    assert original["precedents"][0]["summary"] in text  # P1 accepted
    assert "Not included: 1 unreviewed and 1 rejected." in text
    assert "Review is not complete: 1 finding has not been reviewed" in text
    assert "approved" not in text.lower()
    assert DISCLAIMER in text


def test_each_finding_keeps_its_citation_and_reviewer(
    as_: As, reviewed: AnalysisRun, people: dict[str, User]
) -> None:
    text = text_of(as_("associate").get(brief_url(reviewed)).content)
    assert (
        "Source: SYNTHETIC Plaint.pdf, page 2: “SYNTHETIC: the mark was registered in 2015”" in text
    )
    assert "Asha Rao v. Bharat Traders (SYNTHETIC)" in text
    assert "(SYN) 2019 TEST 101" in text and SYNTHETIC_LABEL in text
    assert "Compared passage: page 3 of the judgment." in text
    assert f"Accepted by {people['lead'].name} on" in text
    assert f"Accepted with the lawyer's wording by {people['lead'].name} on" in text
    assert "Case number: LF-" in text and "Prepared:" in text
    assert "Produced by the scripted test provider: not AI" in text


def test_the_brief_never_holds_notes_or_internal_ids(as_: As, reviewed: AnalysisRun) -> None:
    content = as_("lead").get(brief_url(reviewed)).content
    text = text_of(content)
    assert NOTE not in text
    for internal in (DOC, CHUNK, JUDGMENT, JCHUNK, reviewed.id, SATTVIK):
        assert str(internal) not in text
    document = docx.Document(io.BytesIO(content))
    assert document.core_properties.author == "LexFlow"
    assert NOTE.encode() not in content  # nowhere in the package either


def test_changed_sources_are_flagged_not_replaced(as_: As, reviewed: AnalysisRun) -> None:
    # The fixture's chunks are not in the database: every source counts as changed.
    text = text_of(as_("lead").get(brief_url(reviewed)).content)
    assert text.count(CHANGED_NOTE) == 3  # the fact's source and the contradiction's two
    assert PASSAGE_CHANGED_NOTE in text  # the compared judgment passage
    assert "“SYNTHETIC: the mark was registered in 2015”" in text  # the quote as verified


def test_unchanged_sources_carry_no_flag(
    as_: As, reviewed: AnalysisRun, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(reviews_api, "changed_evidence", lambda session, items: [])
    text = text_of(as_("lead").get(brief_url(reviewed)).content)
    assert CHANGED_NOTE not in text and PASSAGE_CHANGED_NOTE not in text


def test_an_issue_names_facts_left_out(as_: As, run: AnalysisRun) -> None:
    lead = as_("lead")
    decide(lead, run, "F1", "accepted")
    decide(lead, run, "I1", "accepted")
    text = text_of(lead.get(brief_url(run)).content)
    assert "Rests on: F1, F2 (not in this brief)." in text


def test_nothing_accepted_means_no_brief(as_: As, run: AnalysisRun) -> None:
    decide(as_("lead"), run, "F2", "rejected")
    response = as_("lead").get(brief_url(run))
    assert (response.status_code, response.json()["code"]) == (409, "no-accepted-findings")


def test_who_may_export(
    as_: As,
    as_client: As,  # noqa: F811 - the fixture imported from test_portal
    reviewed: AnalysisRun,
) -> None:
    for role in ("admin", "lead", "associate", "paralegal"):
        assert as_(role).get(brief_url(reviewed)).status_code == 200, role
    for outsider in ("other_advocate", "other_paralegal"):
        assert as_(outsider).get(brief_url(reviewed)).status_code == 404
    assert as_client("client").get(brief_url(reviewed)).status_code == 403


def test_the_file_name_is_safe(as_: As, reviewed: AnalysisRun) -> None:
    disposition = as_("lead").get(brief_url(reviewed)).headers["content-disposition"]
    assert disposition.startswith('attachment; filename="case-brief-LF-')
    name = disposition.split('filename="', 1)[1].rstrip('"')
    assert name.endswith(".docx") and all(c.isalnum() or c in "._-" for c in name)


def test_an_export_is_audited_with_counts_only_and_calls_no_model(
    as_: As, db: Session, reviewed: AnalysisRun
) -> None:
    runs_before = db.scalar(select(func.count()).select_from(AnalysisRun))
    as_("lead").get(brief_url(reviewed))
    (event,) = db.scalars(select(AuditEvent).where(AuditEvent.action == "analysis.brief_exported"))
    assert event.details == {"accepted": 2, "edited": 1, "rejected": 1, "unreviewed": 1}
    assert event.target_id == reviewed.id
    assert NOTE not in json.dumps(event.details)
    assert db.scalar(select(func.count()).select_from(AnalysisRun)) == runs_before
