"""Deny by default: every API route needs a signed-in user unless listed as public."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import make_user, sign_in

PUBLIC = {("GET", "/api/health"), ("POST", "/api/auth/login"), ("POST", "/api/auth/logout")}
# Need a session but not a finished password change (so a temporary password can be replaced).
SESSION_ONLY = {("GET", "/api/auth/me"), ("POST", "/api/auth/password")}


def api_routes(app: FastAPI) -> Iterator[tuple[str, str]]:
    """Every API operation, from the OpenAPI document (FastAPI includes routers
    lazily, so ``app.routes`` does not list them)."""
    for path, operations in app.openapi()["paths"].items():
        if path.startswith("/api"):
            for method in sorted(operations):
                yield method.upper(), path


def concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)


def test_the_route_table_is_not_empty(app: FastAPI) -> None:
    assert len(list(api_routes(app))) >= 12
    assert set(api_routes(app)) >= PUBLIC


def test_every_other_route_refuses_anonymous_callers(app: FastAPI, anon_client: TestClient) -> None:
    checked = 0
    for method, path in api_routes(app):
        if (method, path) in PUBLIC:
            continue
        response = anon_client.request(method, concrete(path))
        assert response.status_code == 401, (method, path, response.text)
        assert response.json()["code"] == "not-authenticated"
        checked += 1
    assert checked >= 10


@pytest.mark.parametrize(
    ("method", "path"), [("GET", "/api/no-such-route"), ("DELETE", "/api/cases"), ("GET", "/api")]
)
def test_even_unknown_paths_reveal_nothing_to_anonymous_callers(
    anon_client: TestClient, method: str, path: str
) -> None:
    assert anon_client.request(method, path).status_code == 401


def test_a_well_formed_but_forged_cookie_still_fails(anon_client: TestClient) -> None:
    anon_client.cookies.set("lexflow_session", "A" * 43)  # passes the gate's shape check
    response = anon_client.get("/api/cases")
    assert response.status_code == 401
    assert response.json()["code"] == "not-authenticated"


def test_a_pending_temporary_password_blocks_everything_else(
    app: FastAPI, anon_client: TestClient, db: Session
) -> None:
    user = make_user(db, role="Advocate", must_change_password=True)
    sign_in(anon_client, user)

    for method, path in api_routes(app):
        if (method, path) in PUBLIC | SESSION_ONLY:
            continue
        response = anon_client.request(method, concrete(path))
        assert response.status_code == 403, (method, path, response.text)
        assert response.json()["code"] == "password-change-required"
    assert anon_client.get("/api/auth/me").json()["mustChangePassword"] is True
    assert anon_client.post("/api/auth/logout").status_code == 204
