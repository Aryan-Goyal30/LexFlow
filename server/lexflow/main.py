"""FastAPI application factory.

Run with ``python -m lexflow`` (binds to 127.0.0.1 only). Tests build the app
with ``create_app()`` directly.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from lexflow import __version__
from lexflow.api import cases, documents, health, reference
from lexflow.config import get_settings
from lexflow.errors import CatchAllMiddleware, install_error_handlers
from lexflow.openapi import install_openapi
from lexflow.security import LocalOnlyMiddleware
from lexflow.upload_limit import install_upload_limit

access_logger = logging.getLogger("lexflow.access")

API_PREFIX = "/api"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="LexFlow API",
        version=__version__,
        summary="Case records, reference data and document storage for LexFlow.",
        description=(
            "Phase 1 API. **There is no authentication yet**: run it on 127.0.0.1 only "
            "and never expose it to a network. Sample records are fictional and are "
            "marked with `isSample`."
        ),
    )
    install_error_handlers(app)
    install_openapi(app)

    # Middleware: the last one added runs first. Request order is
    #   access log -> local-only check -> upload size limit -> catch-all -> routes
    # so rejected and failed requests are still logged and get nosniff.
    app.add_middleware(CatchAllMiddleware)
    install_upload_limit(app, settings.max_upload_bytes)
    hosts = list(settings.allowed_hosts)
    if settings.env == "test":
        hosts.append("testserver")  # the host name Starlette's TestClient sends
    app.add_middleware(LocalOnlyMiddleware, allowed_hosts=hosts)

    @app.middleware("http")
    async def _access_log_and_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        # Records which case data was accessed (method, path, status) without
        # bodies, query strings or file contents.
        access_logger.info(
            "%s %s %s %.0fms",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - started) * 1000,
        )
        return response

    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(reference.router, prefix=API_PREFIX)
    app.include_router(cases.router, prefix=API_PREFIX)
    app.include_router(documents.router, prefix=API_PREFIX)
    return app
