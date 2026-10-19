"""RFC 9457 problem-details responses for every error the API returns."""

from __future__ import annotations

import logging
import traceback
from collections.abc import Sequence
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

PROBLEM_MEDIA_TYPE = "application/problem+json"
PROBLEM_BASE = "https://lexflow.invalid/problems/"

logger = logging.getLogger("lexflow.errors")


class FieldError(BaseModel):
    """One invalid field. ``field`` uses the request's camelCase name."""

    field: str
    message: str


class Problem(BaseModel):
    """RFC 9457 problem details, plus LexFlow's ``code`` and ``errors`` members."""

    type: str = Field(description="URI identifying the problem type.")
    title: str
    status: int
    detail: str | None = None
    code: str | None = Field(
        default=None, description="Stable machine-readable reason, e.g. 'duplicate'."
    )
    errors: list[FieldError] = Field(default_factory=list)


class ProblemError(Exception):
    """Raise from route code to return a problem-details response."""

    def __init__(
        self,
        status: int,
        code: str,
        detail: str,
        *,
        title: str | None = None,
        errors: Sequence[FieldError] = (),
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail
        self.title = title or HTTPStatus(status).phrase
        self.errors = list(errors)


def problem_response(
    status: int,
    *,
    code: str | None,
    title: str | None = None,
    detail: str | None = None,
    errors: Sequence[FieldError] = (),
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = Problem(
        type=PROBLEM_BASE + code if code else "about:blank",
        title=title or HTTPStatus(status).phrase,
        status=status,
        detail=detail,
        code=code,
        errors=list(errors),
    )
    return JSONResponse(
        body.model_dump(exclude_none=True),
        status_code=status,
        media_type=PROBLEM_MEDIA_TYPE,
        headers=headers,
    )


def _field_name(loc: Sequence[Any]) -> str:
    # ("body", "title") -> "title"; ("query", "limit") -> "limit"
    parts = [str(p) for p in loc if p not in ("body", "query", "path", "header")]
    return ".".join(parts) or "request"


def _friendly(error: dict[str, Any]) -> str:
    message = str(error.get("msg", "Invalid value."))
    # Pydantic prefixes custom ValueError messages with "Value error, ".
    return message.removeprefix("Value error, ")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemError)
    async def _problem(_: Request, exc: ProblemError) -> JSONResponse:
        return problem_response(
            exc.status, code=exc.code, title=exc.title, detail=exc.detail, errors=exc.errors
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            FieldError(
                # A body that isn't JSON at all has no field; its loc is a byte offset.
                field="request"
                if e.get("type") == "json_invalid"
                else _field_name(e.get("loc", ())),
                message=_friendly(e),
            )
            for e in exc.errors()
        ]
        return problem_response(
            422,
            code="validation-error",
            title="Some fields are invalid",
            detail="Correct the highlighted fields and try again.",
            errors=errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "not-found" if exc.status_code == 404 else None
        detail = exc.detail if isinstance(exc.detail, str) else None
        return problem_response(
            exc.status_code,
            code=code,
            detail=detail,
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        log_unexpected(exc, request.method, request.url.path)
        return internal_error()


def internal_error() -> JSONResponse:
    return problem_response(
        500,
        code="internal-error",
        detail="Something went wrong on the server. Try again later.",
    )


def log_unexpected(exc: BaseException, method: str, path: str) -> None:
    """Log where an error happened without its message.

    Exception messages can contain request data (a database error quotes the
    failing statement's values), so only the type and the stack frames are kept.
    """
    frames = "".join(traceback.format_tb(exc.__traceback__))
    logger.error("Unhandled %s during %s %s\n%s", type(exc).__name__, method, path, frames)


class CatchAllMiddleware:
    """Turn any unhandled exception into a 500 problem response, logged safely.

    Starlette's own error handling re-raises after responding, so the server
    would log the full exception (message included) a second time. Catching
    here, inside the app, stops that and lets outer middleware see a normal
    response.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception as exc:
            log_unexpected(exc, scope["method"], scope["path"])
            if not started:
                await internal_error()(scope, receive, send)


def problem_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI ``responses`` entries describing problem-details errors."""
    return {
        status: {
            "model": Problem,
            "description": HTTPStatus(status).phrase,
            "content": {PROBLEM_MEDIA_TYPE: {}},
        }
        for status in statuses
    }
