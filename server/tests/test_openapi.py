"""The OpenAPI document must describe what the API really returns.

The front end's TypeScript types are generated from it.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

PROBLEM = {"$ref": "#/components/schemas/Problem"}


def _spec(client: TestClient) -> dict[str, Any]:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec: dict[str, Any] = response.json()
    return spec


def test_every_error_response_is_problem_details(client: TestClient) -> None:
    spec = _spec(client)
    checked = 0
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            for code, response in operation["responses"].items():
                if code.startswith(("4", "5")) and code != "503":
                    assert response["content"] == {
                        "application/problem+json": {"schema": PROBLEM}
                    }, f"{method} {path} {code}"
                    checked += 1
    assert checked >= 5


def test_fastapi_validation_schema_is_not_advertised(client: TestClient) -> None:
    schemas = _spec(client)["components"]["schemas"]
    assert "HTTPValidationError" not in schemas
    assert "Problem" in schemas and "FieldError" in schemas


def test_422_only_where_validation_can_fail(client: TestClient) -> None:
    paths = _spec(client)["paths"]
    assert "422" not in paths["/api/cases/{case_id}"]["get"]["responses"]
    assert "422" in paths["/api/cases/{case_id}"]["patch"]["responses"]
    assert "422" in paths["/api/cases"]["post"]["responses"]
    assert "422" in paths["/api/hearings/upcoming"]["get"]["responses"]


def test_contract_uses_camel_case(client: TestClient) -> None:
    schemas = _spec(client)["components"]["schemas"]
    assert set(schemas["CaseCreate"]["properties"]) == {
        "title",
        "clientId",
        "practiceArea",
        "status",
        "priority",
        "leadAdvocateId",
        "courtName",
        "opposingParty",
        "description",
        "nextHearing",
    }
    assert {"nextHearing", "documentCount", "leadAttorney", "isSample"} <= set(
        schemas["CaseSummary"]["required"]
    )
    assert {"hasFile", "downloadUrl", "sizeBytes"} <= set(schemas["DocumentOut"]["required"])
