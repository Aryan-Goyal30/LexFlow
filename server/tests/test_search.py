"""Searching a case's documents: who may, what is searched, what is returned.

``GET /api/cases/{case_id}/search`` (fixtures: access_fixtures). Semantic
search uses ``WordsProvider`` (test-only, not a language model) through the
API's provider dependency; the real model is tested in ``test_embeddings.py``.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from lexflow.api.search import get_search_provider
from lexflow.models import AuditEvent, DocumentChunk, DocumentExtraction, DocumentSection
from lexflow.services import indexing
from tests.access_fixtures import SATTVIK
from tests.embedding_fakes import NOW, WordsProvider, make_ready
from tests.test_portal import OTHER_CASE, as_client, portal_people  # noqa: F401 - fixtures

As = Callable[[str], TestClient]

RENT = "FICTIONAL. The tenant stopped paying rent in March and the arrears grew."
NOTICE = "FICTIONAL. The landlord served a notice to quit on the tenant in May."
TRADEMARK = "FICTIONAL. The trademark was registered in class 30 for biscuits."


@pytest.fixture
def provider(app: FastAPI) -> WordsProvider:
    words = WordsProvider()
    app.dependency_overrides[get_search_provider] = lambda: words
    return words


def add(
    db: Session,
    name: str,
    pages: list[str],
    provider: WordsProvider | None = None,
    case_id: uuid.UUID = SATTVIK,
) -> uuid.UUID:
    document = make_ready(db, case_id, name, pages, chunk_size=200)
    if provider is not None:
        result = indexing.index_document(db, provider, document, batch_size=4, now=lambda: NOW)
        assert result.status == "indexed"
    return document


def search(
    http: TestClient, q: str, mode: str = "semantic", case: Any = SATTVIK, **params: Any
) -> Any:
    return http.get(f"/api/cases/{case}/search", params={"q": q, "mode": mode, **params})


@pytest.fixture
def corpus(db: Session, people: Any, provider: WordsProvider) -> dict[str, uuid.UUID]:
    return {
        "lease": add(db, "Lease dispute.pdf", [RENT, NOTICE], provider),
        "brand": add(db, "Trademark.pdf", [TRADEMARK], provider),
    }


# --- who may search ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("admin", 200),
        ("lead", 200),
        ("associate", 200),
        ("paralegal", 200),
        ("other_advocate", 404),
        ("other_paralegal", 404),
    ],
)
def test_staff_who_may_view_the_case_may_search_it(
    as_: As, corpus: dict[str, uuid.UUID], role: str, expected: int
) -> None:
    for mode in ("keyword", "semantic", "hybrid"):
        response = search(as_(role), "tenant rent", mode)
        assert response.status_code == expected, (mode, response.text)
        if expected == 404:
            assert response.json()["code"] == "case-not-found"
            assert "tenant" not in response.text.lower()


def test_client_accounts_and_anonymous_callers_cannot_search(
    as_client: As,  # noqa: F811 - the fixture imported from test_portal
    anon_client: TestClient,
    corpus: dict[str, uuid.UUID],
) -> None:
    assert search(as_client("client"), "tenant").status_code == 403  # their own case, still no
    assert search(anon_client, "tenant").status_code == 401


# --- what is searched -------------------------------------------------------------------


def test_semantic_results_come_best_first_with_exact_attribution(
    as_: As, db: Session, corpus: dict[str, uuid.UUID], provider: WordsProvider
) -> None:
    body = search(as_("paralegal"), "tenant arrears rent").json()
    assert body["mode"] == "semantic" and body["model"] == provider.model
    assert (body["documentsWithText"], body["documentsIndexed"]) == (2, 2)
    top = body["results"][0]
    assert top["documentId"] == str(corpus["lease"]) and top["documentName"] == "Lease dispute.pdf"
    assert top["pageNumber"] == 1 and "arrears" in top["text"]
    scores = [r["score"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True)
    for result in body["results"]:
        section = db.get(
            DocumentSection, (uuid.UUID(result["documentId"]), result["sectionNumber"])
        )
        assert section is not None
        assert section.text[result["charStart"] : result["charEnd"]] == result["text"]


def test_keyword_search_works_without_embeddings(as_: As, db: Session, people: Any) -> None:
    add(db, "Lease dispute.pdf", [RENT, NOTICE])  # extracted, never indexed
    body = search(as_("lead"), "notice to quit", "keyword").json()
    assert body["model"] is None and body["documentsIndexed"] == 0
    assert [r["pageNumber"] for r in body["results"]] == [2]
    assert search(as_("lead"), "biscuits", "keyword").json()["results"] == []


def test_hybrid_merges_both_rankings(as_: As, corpus: dict[str, uuid.UUID]) -> None:
    body = search(as_("lead"), "trademark class 30", "hybrid").json()
    assert body["mode"] == "hybrid"
    assert body["results"][0]["documentId"] == str(corpus["brand"])


def test_deleted_documents_are_never_searched(as_: As, corpus: dict[str, uuid.UUID]) -> None:
    assert as_("lead").delete(f"/api/documents/{corpus['brand']}").status_code == 204
    for mode in ("keyword", "semantic", "hybrid"):
        body = search(as_("lead"), "trademark biscuits", mode).json()
        assert all(r["documentId"] != str(corpus["brand"]) for r in body["results"]), mode
        assert body["documentsWithText"] == 1
    as_("lead").post(f"/api/documents/{corpus['brand']}/restore")
    assert search(as_("lead"), "trademark biscuits").json()["results"][0]["documentId"] == str(
        corpus["brand"]
    )


def test_other_cases_documents_never_appear(
    as_: As, db: Session, corpus: dict[str, uuid.UUID], provider: WordsProvider
) -> None:
    elsewhere = add(db, "Other lease.pdf", [RENT], provider, case_id=OTHER_CASE)
    for mode in ("keyword", "semantic", "hybrid"):
        body = search(as_("admin"), "tenant rent arrears", mode).json()
        assert all(r["documentId"] != str(elsewhere) for r in body["results"]), mode


def test_an_archived_case_stays_searchable(as_: As, corpus: dict[str, uuid.UUID]) -> None:
    as_("admin").post(f"/api/cases/{SATTVIK}/archive")
    assert search(as_("lead"), "tenant").status_code == 200


def test_text_being_extracted_again_is_not_searched(
    as_: As, db: Session, corpus: dict[str, uuid.UUID]
) -> None:
    db.execute(
        update(DocumentExtraction)
        .where(DocumentExtraction.document_id == corpus["lease"])
        .values(status="queued", index_status="disabled", finished_at=None, attempts=0)
    )
    db.commit()
    for mode in ("keyword", "semantic"):
        body = search(as_("lead"), "tenant rent", mode).json()
        assert all(r["documentId"] != str(corpus["lease"]) for r in body["results"]), mode


def test_vectors_of_another_model_are_never_compared(
    as_: As, db: Session, people: Any, provider: WordsProvider
) -> None:
    other = WordsProvider("another-model@9")  # same arithmetic, different model name
    document = add(db, "Indexed elsewhere.pdf", [RENT], other)
    body = search(as_("lead"), "tenant rent arrears").json()
    assert all(r["documentId"] != str(document) for r in body["results"])
    assert (body["documentsWithText"], body["documentsIndexed"]) == (1, 0)


def test_a_vector_of_old_text_is_not_used(
    as_: As, db: Session, corpus: dict[str, uuid.UUID]
) -> None:
    chunk = db.scalars(
        select(DocumentChunk).where(DocumentChunk.document_id == corpus["brand"])
    ).first()
    assert chunk is not None
    chunk.content_sha256 = "e" * 64  # the text changed since it was embedded
    db.commit()
    body = search(as_("lead"), "trademark biscuits class").json()
    assert all(r["chunkId"] != str(chunk.id) for r in body["results"])


# --- refusals and audit -------------------------------------------------------------------


def test_semantic_search_says_why_it_is_unavailable(
    app: FastAPI, as_: As, db: Session, people: Any
) -> None:
    app.dependency_overrides[get_search_provider] = lambda: "Semantic search is off: test."
    for mode in ("semantic", "hybrid"):
        response = search(as_("lead"), "tenant", mode)
        assert (response.status_code, response.json()["code"]) == (
            409,
            "semantic-search-unavailable",
        )
        assert response.json()["detail"] == "Semantic search is off: test."
    assert search(as_("lead"), "tenant", "keyword").status_code == 200


def test_requests_are_validated(as_: As, corpus: dict[str, uuid.UUID]) -> None:
    http = as_("lead")
    assert search(http, "   ").json()["code"] == "query-empty"
    assert search(http, "x" * 501).status_code == 422
    assert search(http, "tenant", limit=0).status_code == 422
    assert search(http, "tenant", limit=51).status_code == 422
    assert search(http, "tenant", mode="magic").status_code == 422
    assert len(search(http, "fictional", limit=1).json()["results"]) == 1
    assert search(http, "tenant", case="not-a-uuid").status_code == 404


def test_each_search_is_audited_without_the_query(
    as_: As, db: Session, corpus: dict[str, uuid.UUID], people: Any
) -> None:
    search(as_("paralegal"), "secret strategy words", "hybrid", limit=5)
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "case.searched")).one()
    assert event.actor_id == people["paralegal"].id and event.case_id == SATTVIK
    assert event.details["mode"] == "hybrid" and event.details["limit"] == 5
    assert "secret" not in str(event.details)
