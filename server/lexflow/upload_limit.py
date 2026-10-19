"""Reject oversized uploads while the request body is still streaming in.

Applies to ``POST /api/cases/{id}/documents``. A declared ``Content-Length``
over the limit is refused before any body is read; otherwise bytes are counted
as they arrive and the request is stopped as soon as it passes the limit, so a
huge upload is never fully received. The document service then checks the
file's exact size against the same limit.
"""

from __future__ import annotations

import re
from contextlib import suppress
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from lexflow.errors import problem_response
from lexflow.services.formatting import format_file_size

UPLOAD_PATH = re.compile(r"^/api/cases/[^/]+/documents/?$")
# Room for multipart boundaries and part headers around the file itself.
MULTIPART_OVERHEAD = 64 * 1024


class BodyTooLargeError(Exception):
    pass


def _detail(limit: int) -> str:
    return f"This file is larger than the {format_file_size(limit)} upload limit."


class UploadLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or not UPLOAD_PATH.match(scope["path"])
        ):
            await self.app(scope, receive, send)
            return

        limit: int = scope["app"].state.upload_limit
        allowed = limit + MULTIPART_OVERHEAD
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > allowed:
            await problem_response(413, code="too-large", detail=_detail(limit))(
                scope, receive, send
            )
            return

        received = 0
        exceeded = False
        replied = False
        too_large = problem_response(413, code="too-large", detail=_detail(limit))

        async def counting_receive() -> Message:
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > allowed:
                    exceeded = True
                    raise BodyTooLargeError
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal replied
            if exceeded:
                # The framework turns the aborted body into its own error (e.g. a
                # 400 from the form parser). Answer with the 413 instead, once.
                if not replied and message["type"] == "http.response.start":
                    replied = True
                    await too_large(scope, receive, send)
                return
            await send(message)

        with suppress(BodyTooLargeError):
            await self.app(scope, counting_receive, guarded_send)
        if exceeded and not replied:
            await too_large(scope, receive, send)


def install_upload_limit(app: Any, limit: int) -> None:
    app.state.upload_limit = limit
    app.add_middleware(UploadLimitMiddleware)
