"""The top bar's quick search (``GET /api/search``): cases, clients and documents.

It must show only what the lists would show: cases by case visibility, clients
of visible cases (Administrators: all), live documents of visible cases; never
to Client accounts. Wildcards in the query are taken literally.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from lexflow.models import Case, Document, User
from tests.access_fixtures import SATTVIK
from tests.test_portal import as_client, portal_people  # noqa: F401 - fixtures

As = Callable[[str], TestClient]


def search(http: TestClient, q: str) -> dict[str, list[dict[str, str]]]:
    response = http.get("/api/search", params={"q": q})
    assert response.status_code == 200, response.text
    body: dict[str, list[dict[str, str]]] = response.json()
    return body


def sattvik_document(db: Session) -> Document:
    document = db.scalars(
        select(Document)
        .where(Document.case_id == SATTVIK, Document.deleted_at.is_(None))
        .order_by(Document.name)
    ).first()
    assert document is not None, "the sample data has documents on the Sattvik case"
    return document


def test_a_team_member_finds_their_case_its_client_and_its_documents(as_: As, db: Session) -> None:
    case = db.get(Case, SATTVIK)
    assert case is not None
    found = search(as_("paralegal"), "Sattvik")
    assert [c["id"] for c in found["cases"]] == [str(SATTVIK)]
    assert found["cases"][0]["caseNumber"] == case.case_number
    assert {c["id"] for c in found["clients"]} <= {str(case.client_id)}

    document = sattvik_document(db)
    hits = search(as_("paralegal"), document.name[:6])["documents"]
    assert str(document.id) in {d["id"] for d in hits}
    assert all(d["caseId"] == str(SATTVIK) for d in hits), "only documents of visible cases"


def test_nothing_outside_your_cases_is_found(as_: As, db: Session) -> None:
    document = sattvik_document(db)
    for q in ("Sattvik", document.name[:6], "LF-2026"):
        found = search(as_("other_paralegal"), q)
        assert found == {"cases": [], "clients": [], "documents": []}, q


def test_an_administrator_searches_every_case(as_: As, db: Session) -> None:
    total = len(db.scalars(select(Case.id).where(Case.case_number.like("LF-2026%"))).all())
    visible = search(as_("admin"), "LF-2026")["cases"]
    assert total > 1 and len(visible) == min(total, 5), "every case, at most five by default"
    assert all(c["caseNumber"].startswith("LF-2026") for c in visible)
    assert len(search(as_("paralegal"), "LF-2026")["cases"]) == 1, "the paralegal's one case"


def test_deleted_documents_are_never_found(as_: As, db: Session) -> None:
    document = sattvik_document(db)
    document.deleted_at = datetime.now(UTC)
    db.commit()
    hits = search(as_("lead"), document.name)["documents"]
    assert str(document.id) not in {d["id"] for d in hits}


def test_wildcards_are_literal_and_short_queries_are_refused(as_: As) -> None:
    assert search(as_("admin"), "%%") == {"cases": [], "clients": [], "documents": []}
    assert search(as_("admin"), "__") == {"cases": [], "clients": [], "documents": []}
    assert as_("admin").get("/api/search", params={"q": "a"}).status_code == 422


def test_client_accounts_cannot_search(
    as_client: As,  # noqa: F811 - the fixture imported from test_portal
    portal_people: dict[str, User],  # noqa: F811
) -> None:
    assert as_client("client").get("/api/search", params={"q": "Sattvik"}).status_code == 403
