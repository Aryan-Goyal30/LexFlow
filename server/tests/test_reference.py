from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from lexflow.models import Client, User
from lexflow.seed import sample_uuid
from lexflow.seed.loader import load_sample_data


def test_empty_database_returns_empty_lists(client: TestClient) -> None:
    assert client.get("/api/clients").json() == []
    assert client.get("/api/advocates").json() == []


def test_clients_are_sorted_camel_case_and_marked_sample(client: TestClient, db: Session) -> None:
    load_sample_data(db)

    response = client.get("/api/clients")

    assert response.status_code == 200
    clients = response.json()
    assert len(clients) == 6
    assert [c["name"] for c in clients] == sorted(c["name"] for c in clients)
    first = next(c for c in clients if c["id"] == str(sample_uuid("client", "c-001")))
    assert first == {
        "id": str(sample_uuid("client", "c-001")),
        "name": "Aarav Textiles Pvt. Ltd.",
        "email": "legal@aarav-textiles.example",
        "phone": "+91 00000 00001",
        "company": "Aarav Textiles Pvt. Ltd., Mumbai",
        "isSample": True,
    }
    no_company = next(c for c in clients if c["name"] == "Suresh Iyer")
    assert no_company["company"] is None


def test_advocates_only_include_the_advocate_role(client: TestClient, db: Session) -> None:
    load_sample_data(db)
    db.add(User(name="A Paralegal", email=None, role="Paralegal"))
    db.add(Client(name="Real Client", email="client@example.invalid", phone="000"))
    db.flush()

    advocates = client.get("/api/advocates").json()

    assert [a["name"] for a in advocates] == [
        "Aryan Goyal",
        "Farhan Qureshi",
        "Meera Nair",
        "Rajat Deshpande",
        "Vikram Sethi",
    ]
    aryan = advocates[0]
    assert aryan == {
        "id": str(sample_uuid("advocate", "Aryan Goyal")),
        "name": "Aryan Goyal",
        "email": "aryan.goyal@lexflow.test",
        "isSample": True,
    }
    # Every sample advocate has a fictional address on the reserved .test domain.
    assert all(a["email"].endswith("@lexflow.test") for a in advocates)

    real = next(c for c in client.get("/api/clients").json() if c["name"] == "Real Client")
    assert real["isSample"] is False
