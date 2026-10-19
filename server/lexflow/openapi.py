"""Make the OpenAPI document describe the errors the API really returns.

FastAPI documents validation failures with its own ``HTTPValidationError``
shape, but every LexFlow error is an RFC 9457 ``Problem``. This post-processing
step:

- describes every 4xx/5xx response as ``application/problem+json`` with the
  ``Problem`` schema;
- removes the automatic 422 from operations that cannot fail validation (no
  request body and only unconstrained string path parameters);
- removes FastAPI's unused validation-error schemas.

The front end's TypeScript types are generated from this document, so its
accuracy matters.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from lexflow.errors import PROBLEM_MEDIA_TYPE

PROBLEM_REF = {"$ref": "#/components/schemas/Problem"}


def _can_fail_validation(operation: dict[str, Any]) -> bool:
    if "requestBody" in operation:
        return True
    for parameter in operation.get("parameters", []):
        schema = parameter.get("schema", {})
        unconstrained_string = schema.get("type") == "string" and not (
            set(schema) - {"type", "title", "description"}
        )
        if parameter.get("in") != "path" or not unconstrained_string:
            return True
    return False


def _problem_response(response: dict[str, Any]) -> dict[str, Any]:
    return {
        "description": response.get("description", "Error"),
        "content": {PROBLEM_MEDIA_TYPE: {"schema": PROBLEM_REF}},
    }


def build_openapi(app: FastAPI) -> dict[str, Any]:
    spec = get_openapi(
        title=app.title,
        version=app.version,
        summary=app.summary,
        description=app.description,
        routes=app.routes,
    )
    for path_item in spec.get("paths", {}).values():
        for operation in path_item.values():
            responses: dict[str, Any] = operation.get("responses", {})
            if "422" in responses and not _can_fail_validation(operation):
                del responses["422"]
            for code, response in list(responses.items()):
                if code[0] in "45" and code != "503":
                    responses[code] = _problem_response(response)

    schemas = spec.get("components", {}).get("schemas", {})
    for unused in ("HTTPValidationError", "ValidationError"):
        schemas.pop(unused, None)
    return spec


def install_openapi(app: FastAPI) -> None:
    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            app.openapi_schema = build_openapi(app)
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]
