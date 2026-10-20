"""The judgment collection API: access, browsing, search, reading, isolation.

The collection is the SYNTHETIC fixture set imported through the real
importer. Semantic search uses ``WordsProvider`` (test-only, not a language
model) through the API's provider dependency.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lexflow.api.search import get_search_provider
from lexflow.extraction import Extracted, Limits, extract
from lexflow.models import AuditEvent, Judgment, JudgmentChunk, JudgmentSection
from lexflow.services import judgment_import as importer
from lexflow.services import judgments as service
from tests.access_fixtures import SATTVIK
from tests.embedding_fakes import WordsProvider
from tests.test_portal import as_client, portal_people  # noqa: F401 - fixtures

As = Callable[[str], TestClient]
MANIFEST = Path(__file__).parent / "fixtures" / "judgments" / "synthetic" / "manifest.json"
NOW = datetime(2026, 6, 1, tzinfo=UTC)
STAFF = ("admin", "lead", "associate", "paralegal", "other_advocate", "other_paralegal")


def jid(source_id: str) -> str:
    return str(importer.judgment_id("lexflow-synthetic", source_id))


def in_process(content_type: str, data: bytes, limits: Limits, timeout: float) -> Extracted:
    return extract(content_type, data, limits)


@pytest.fixture
def collection(db: Session, people: Any) -> None:
    plan = importer.plan_import(db, MANIFEST, max_bytes=10_000_000)
    outcome = importer.apply_import(
        db,
        plan,
        update=False,
        limits=Limits(max_pages=100, max_text_bytes=1_000_000, max_unpacked_bytes=10_000_000),
        timeout_seconds=30,
        extract=in_process,
        operator="test",
        now=NOW,
    )
    assert len(outcome.imported) == 13 and not outcome.rejected


@pytest.fixture
def words(app: FastAPI) -> WordsProvider:
    provider = WordsProvider()
    app.dependency_overrides[get_search_provider] = lambda: provider
    return provider


def index_all(db: Session, provider: WordsProvider) -> None:
    for judgment_id in db.scalars(select(Judgment.id)):
        service.index_judgment(db, provider, judgment_id, batch_size=8, now=lambda: NOW)


def search(http: TestClient, q: str, **params: Any) -> Any:
    return http.get("/api/judgments/search", params={"q": q, **params})


# --- who may use the collection -------------------------------------------------------------


@pytest.mark.parametrize("role", STAFF)
def test_every_staff_role_may_use_the_collection(as_: As, collection: None, role: str) -> None:
    http = as_(role)
    assert http.get("/api/judgments/facets").status_code == 200
    assert http.get("/api/judgments").status_code == 200
    assert search(http, "rent").status_code == 200
    assert http.get(f"/api/judgments/{jid('syn-001')}").status_code == 200
    assert http.get(f"/api/judgments/{jid('syn-001')}/text").status_code == 200


def test_clients_and_anonymous_callers_are_refused(
    as_client: As,  # noqa: F811 - the fixture imported from test_portal
    anon_client: TestClient,
    collection: None,
) -> None:
    paths = [
        "/api/judgments/facets",
        "/api/judgments",
        "/api/judgments/search?q=rent",
        f"/api/judgments/{jid('syn-001')}",
        f"/api/judgments/{jid('syn-001')}/text",
    ]
    for path in paths:
        assert as_client("client").get(path).status_code == 403, path
        response = anon_client.get(path)
        assert response.status_code == 401, path
        assert "Asha" not in response.text


# --- browsing ----------------------------------------------------------------------------------


def test_browsing_is_newest_first_with_undated_last_and_stable_pages(
    as_: As, collection: None
) -> None:
    http = as_("lead")
    body = http.get("/api/judgments", params={"pageSize": 50}).json()
    assert body["total"] == 13 and len(body["items"]) == 13
    dates = [item["decisionDate"] for item in body["items"]]
    assert dates[:-1] == sorted(dates[:-1], reverse=True) and dates[-1] is None
    assert body["items"][0]["synthetic"] is True
    paged = [
        item["id"]
        for page in (1, 2, 3)
        for item in http.get("/api/judgments", params={"pageSize": 5, "page": page}).json()["items"]
    ]
    assert paged == [item["id"] for item in body["items"]]
    assert http.get("/api/judgments", params={"page": 9}).json()["items"] == []


def test_browsing_filters_by_court_and_years(as_: As, collection: None) -> None:
    http = as_("lead")
    district = http.get(
        "/api/judgments", params={"court": "SYNTHETIC District Court (test fixture)"}
    ).json()
    assert district["total"] == 5 and {i["court"] for i in district["items"]} == {
        "SYNTHETIC District Court (test fixture)"
    }
    years = http.get("/api/judgments", params={"yearFrom": 2020, "yearTo": 2021}).json()
    assert {i["year"] for i in years["items"]} == {2020, 2021} and years["total"] == 3
    bad = http.get("/api/judgments", params={"yearFrom": 2022, "yearTo": 2020})
    assert (bad.status_code, bad.json()["code"]) == (422, "invalid-years")
    assert http.get("/api/judgments", params={"pageSize": 51}).status_code == 422
    assert http.get("/api/judgments", params={"yearFrom": 1700}).status_code == 422


def test_facets_describe_the_collection(as_: As, collection: None) -> None:
    body = as_("lead").get("/api/judgments/facets").json()
    assert (body["total"], body["synthetic"], body["indexed"]) == (13, 13, 0)
    assert body["courts"] == [
        "SYNTHETIC District Court (test fixture)",
        "SYNTHETIC High Court (test fixture)",
    ]
    assert (body["yearMin"], body["yearMax"]) == (2015, 2024)
    assert body["modes"]["keyword"] is True


# --- keyword search ------------------------------------------------------------------------------


def test_keyword_search_ranks_judgments_with_exact_passages(
    as_: As, db: Session, collection: None
) -> None:
    body = search(as_("paralegal"), "deceptively similar mark").json()
    assert body["mode"] == "keyword" and body["model"] is None
    top = body["results"][0]
    assert top["judgment"]["id"] == jid("syn-003")
    assert top["judgment"]["citation"] == "(SYN) 2018 TEST 103"
    assert top["judgment"]["sourceUrl"] == "https://judgments.lexflow.invalid/syn-003"
    passage = top["passage"]
    section = db.get(JudgmentSection, (uuid.UUID(jid("syn-003")), passage["sectionNumber"]))
    assert section is not None
    assert section.text[passage["charStart"] : passage["charEnd"]] == passage["text"]
    ids = [r["judgment"]["id"] for r in body["results"]]
    assert len(ids) == len(set(ids))  # one result per judgment
    scores = [r["score"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True)


def test_the_same_query_always_gives_the_same_order(as_: As, collection: None) -> None:
    http = as_("lead")
    first = [r["judgment"]["id"] for r in search(http, "court held", pageSize=20).json()["results"]]
    for _ in range(3):
        again = [
            r["judgment"]["id"] for r in search(http, "court held", pageSize=20).json()["results"]
        ]
        assert again == first


def test_pages_split_one_ranking_without_gaps_or_repeats(as_: As, collection: None) -> None:
    http = as_("lead")
    whole = search(http, "court held", pageSize=20).json()
    pieces = [
        r["judgment"]["id"]
        for page in (1, 2, 3, 4)
        for r in search(http, "court held", pageSize=4, page=page).json()["results"]
    ]
    assert pieces == [r["judgment"]["id"] for r in whole["results"]][: len(pieces)]
    assert whole["total"] == len(whole["results"]) and whole["maxResults"] == 100
    assert search(http, "court held", page=10).json()["results"] == []
    assert search(http, "court held", page=11).status_code == 422
    assert search(http, "court held", pageSize=21).status_code == 422


def test_filters_narrow_the_search(as_: As, collection: None) -> None:
    body = search(as_("lead"), "bail", yearFrom=2021, yearTo=2021).json()
    assert {r["judgment"]["id"] for r in body["results"]} == {jid("syn-004"), jid("syn-010")}
    body = search(as_("lead"), "bail", court="SYNTHETIC District Court (test fixture)").json()
    assert all(
        r["judgment"]["court"] == "SYNTHETIC District Court (test fixture)" for r in body["results"]
    )


def test_a_query_with_no_match_returns_nothing(as_: As, collection: None) -> None:
    body = search(as_("lead"), "spaceship asteroid").json()
    assert (body["total"], body["results"]) == (0, [])


@pytest.mark.parametrize(
    "query",
    [
        "'; DROP TABLE judgments; --",
        "<script>alert(1)</script>",
        "rent & | ! :* (( ))",
        '"unbalanced quote',
        "the and of",
        "किराया बकाया",
        "-rent",
        "x" * 300,
    ],
)
def test_hostile_or_odd_queries_are_harmless(
    as_: As, db: Session, collection: None, query: str
) -> None:
    response = search(as_("lead"), query)
    assert response.status_code == 200, response.text
    assert db.scalar(select(func.count()).select_from(Judgment)) == 13  # nothing dropped
    for hit in response.json()["results"]:
        assert "<script>" not in hit["passage"]["text"]


def test_invalid_search_requests_are_refused(as_: As, collection: None) -> None:
    http = as_("lead")
    assert search(http, "   ").json()["code"] == "query-empty"
    assert search(http, "x" * 301).status_code == 422
    assert http.get("/api/judgments/search").status_code == 422
    assert search(http, "rent", mode="magic").status_code == 422
    assert search(http, "rent", yearFrom=2024, yearTo=2010).json()["code"] == "invalid-years"


# --- semantic and hybrid --------------------------------------------------------------------------


def test_semantic_and_hybrid_need_embeddings(app: FastAPI, as_: As, collection: None) -> None:
    app.dependency_overrides[get_search_provider] = lambda: "Semantic search is off: test."
    for mode in ("semantic", "hybrid"):
        response = search(as_("lead"), "rent", mode=mode)
        assert (response.status_code, response.json()["code"]) == (
            409,
            "semantic-search-unavailable",
        )
    modes = as_("lead").get("/api/judgments/facets").json()["modes"]
    assert modes == {
        "keyword": True,
        "semantic": False,
        "hybrid": False,
        "unavailableReason": "Semantic search is off: test.",
        "model": None,
    }


def test_semantic_search_uses_current_vectors_only(
    as_: As, db: Session, collection: None, words: WordsProvider
) -> None:
    http = as_("lead")
    assert search(http, "tenant rent arrears", mode="semantic").json()["total"] == 0  # no vectors
    index_all(db, words)
    body = search(http, "tenant rent arrears repairs", mode="semantic").json()
    assert body["model"] == words.model and body["results"][0]["judgment"]["id"] == jid("syn-001")
    assert as_("lead").get("/api/judgments/facets").json()["indexed"] == 13

    chunk = db.scalars(
        select(JudgmentChunk).where(JudgmentChunk.judgment_id == uuid.UUID(jid("syn-001")))
    ).first()
    assert chunk is not None
    chunk.content_sha256 = "a" * 64  # its text changed after it was embedded
    db.commit()
    body = search(http, "tenant rent arrears repairs", mode="semantic").json()
    assert all(r["judgment"]["id"] != jid("syn-001") for r in body["results"])


def test_vectors_of_another_model_are_not_used(
    as_: As, db: Session, collection: None, words: WordsProvider
) -> None:
    index_all(db, WordsProvider("another-model@9"))
    assert search(as_("lead"), "tenant rent", mode="semantic").json()["total"] == 0


def test_hybrid_merges_keyword_and_semantic(
    as_: As, db: Session, collection: None, words: WordsProvider
) -> None:
    index_all(db, words)
    body = search(as_("lead"), "trademark biscuits injunction", mode="hybrid").json()
    assert body["mode"] == "hybrid" and body["results"][0]["judgment"]["id"] == jid("syn-003")
    ids = [r["judgment"]["id"] for r in body["results"]]
    assert len(ids) == len(set(ids))


# --- reading --------------------------------------------------------------------------------------


def test_a_judgment_shows_its_source_and_terms(as_: As, collection: None) -> None:
    body = as_("associate").get(f"/api/judgments/{jid('syn-006')}").json()
    assert body["title"] == "Leela Thomas v. Vinod Pillai (SYNTHETIC)"
    assert body["bench"] == "SYNTHETIC J." and body["sectionCount"] == 1
    assert body["source"] == {
        "key": "lexflow-synthetic",
        "name": "LexFlow synthetic test judgments",
        "termsUrl": "https://terms.lexflow.invalid/synthetic",
        "termsCheckedOn": "2026-10-20",
        "termsCheckedBy": "LexFlow developers",
        "permittedUse": "Invented for automated tests only. Not real judgments; never cite.",
        "synthetic": True,
    }
    bare = as_("lead").get(f"/api/judgments/{jid('syn-013')}").json()
    assert (bare["citation"], bare["decisionDate"], bare["year"], bare["bench"]) == (
        None,
        None,
        None,
        None,
    )


def test_reading_a_judgments_text(as_: As, collection: None) -> None:
    http = as_("lead")
    body = http.get(f"/api/judgments/{jid('syn-004')}/text").json()
    assert body["synthetic"] is True and "custodial interrogation" in body["section"]["text"]
    beyond = http.get(f"/api/judgments/{jid('syn-004')}/text", params={"section": 2})
    assert (beyond.status_code, beyond.json()["code"]) == (404, "section-not-found")
    assert (
        http.get(f"/api/judgments/{jid('syn-004')}/text", params={"section": 0}).status_code == 422
    )


def test_unknown_judgments_are_not_found(as_: As, collection: None) -> None:
    http = as_("lead")
    for raw in (str(uuid.uuid4()), "not-a-uuid", "1;DROP"):
        response = http.get(f"/api/judgments/{raw}")
        assert (response.status_code, response.json()["code"]) == (404, "judgment-not-found")


# --- isolation and audit --------------------------------------------------------------------------


def test_private_case_documents_never_appear_in_judgment_search(
    as_: As, db: Session, collection: None
) -> None:
    from tests.embedding_fakes import make_ready

    make_ready(db, SATTVIK, "Private.pdf", ["CONFIDENTIAL zyxwvut strategy memo for the client."])
    assert search(as_("admin"), "zyxwvut").json()["total"] == 0
    case = as_("admin").get(f"/api/cases/{SATTVIK}/search", params={"q": "deceptively similar"})
    assert case.json()["results"] == []  # and case search never returns judgments


def test_judgment_searches_are_audited_without_the_query(
    as_: As, db: Session, collection: None, people: Any
) -> None:
    search(as_("paralegal"), "confidential strategy words", page=2)
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "judgment.searched")).one()
    assert event.actor_id == people["paralegal"].id
    assert event.details == {"mode": "keyword", "results": 0, "page": 2}
    assert "confidential" not in str(event.details)
