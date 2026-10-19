from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from lexflow.db import get_engine


def test_health_reports_database_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    assert response.headers["x-content-type-options"] == "nosniff"


def test_health_reports_unreachable_database(app: FastAPI) -> None:
    # Nothing listens on port 1; the check must fail fast and say so.
    unreachable = create_engine(
        "postgresql+psycopg://nobody:nothing@127.0.0.1:1/none",
        connect_args={"connect_timeout": 2},
    )
    app.dependency_overrides[get_engine] = lambda: unreachable
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}
    # The response must not leak connection details.
    assert "nobody" not in response.text and "127.0.0.1" not in response.text


def test_unknown_route_is_problem_details(client: TestClient) -> None:
    response = client.get("/api/no-such-route")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["status"] == 404
    assert body["code"] == "not-found"
    assert body["type"].endswith("/not-found")


def test_openapi_and_docs_are_served(client: TestClient) -> None:
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    assert schema.json()["info"]["title"] == "LexFlow API"
    assert "/api/health" in schema.json()["paths"]

    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "swagger" in docs.text.lower()
