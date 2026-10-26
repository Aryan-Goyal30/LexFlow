"""FastAPI application factory.

Run with ``python -m lexflow`` (binds to 127.0.0.1 only). Tests build the app
with ``create_app()`` directly.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import Depends, FastAPI, Request, Response

from lexflow import __version__
from lexflow.api import (
    admin,
    analysis,
    assessments,
    auth,
    cases,
    clients,
    demo,
    documents,
    health,
    hearings,
    judgments,
    portal,
    reference,
    reviews,
    search,
)
from lexflow.auth.deps import require_roles, require_user
from lexflow.auth.gate import SessionGateMiddleware
from lexflow.config import get_settings
from lexflow.domain import ADMINISTRATOR, CLIENT, STAFF_ROLES
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
    #   access log -> local-only check (Host, CSRF) -> session gate
    #   -> upload size limit -> catch-all -> routes
    # so rejected and failed requests are still logged and get nosniff, and no
    # request body is read before the caller has shown a session cookie.
    app.add_middleware(CatchAllMiddleware)
    install_upload_limit(app, settings.max_upload_bytes)
    app.add_middleware(SessionGateMiddleware, session_cookie=settings.session_cookie_name)
    hosts = list(settings.allowed_hosts)
    if settings.env == "test":
        hosts.append("testserver")  # the host name Starlette's TestClient sends
    app.add_middleware(
        LocalOnlyMiddleware,
        allowed_hosts=hosts,
        allowed_origins=settings.allowed_origins,
        session_cookie=settings.session_cookie_name,
    )

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
    app.include_router(auth.router, prefix=API_PREFIX)
    # Everything but health and sign-in needs a signed-in user (who has no
    # pending temporary password). These routers are for staff; routes add
    # per-case and per-field checks on top (lexflow.authz).
    staff = [Depends(require_user), Depends(require_roles(*STAFF_ROLES))]
    app.include_router(reference.router, prefix=API_PREFIX, dependencies=staff)
    # After reference: /clients/options must win over /clients/{client_id}.
    app.include_router(clients.router, prefix=API_PREFIX, dependencies=staff)
    app.include_router(demo.router, prefix=API_PREFIX, dependencies=staff)
    app.include_router(cases.router, prefix=API_PREFIX, dependencies=staff)
    app.include_router(documents.router, prefix=API_PREFIX, dependencies=staff)
    app.include_router(search.router, prefix=API_PREFIX, dependencies=staff)
    app.include_router(analysis.router, prefix=API_PREFIX, dependencies=staff)
    app.include_router(reviews.router, prefix=API_PREFIX, dependencies=staff)
    app.include_router(assessments.router, prefix=API_PREFIX, dependencies=staff)
    app.include_router(judgments.router, prefix=API_PREFIX, dependencies=staff)
    app.include_router(hearings.router, prefix=API_PREFIX, dependencies=staff)
    administrators = [Depends(require_user), Depends(require_roles(ADMINISTRATOR))]
    app.include_router(admin.router, prefix=API_PREFIX, dependencies=administrators)
    # The client portal: Client accounts only (and they reach nothing above).
    clients_only = [Depends(require_user), Depends(require_roles(CLIENT))]
    app.include_router(portal.router, prefix=API_PREFIX, dependencies=clients_only)
    return app
