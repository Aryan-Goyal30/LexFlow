"""The first line of authentication: no session cookie, no API.

Runs before the request body is read, so an anonymous caller cannot make the
server receive and spool a large upload (FastAPI reads declared body
parameters before it runs dependencies). It only checks that a well-formed
session cookie is present; the ``require_user`` dependency then checks the
session in the database and loads the user. Both layers must agree, so a router
mounted without ``require_user`` is still not open to anonymous callers, and a
forged cookie still fails at the second layer.

Public: ``GET /api/health``, ``POST /api/auth/login`` and ``POST /api/auth/logout``.
Everything else under ``/api`` answers 401 ``not-authenticated`` without a
session, including paths that do not exist (no anonymous route discovery).
"""

from __future__ import annotations

from http.cookies import CookieError, SimpleCookie

from starlette.types import ASGIApp, Receive, Scope, Send

from lexflow.auth.sessions import looks_like_token
from lexflow.errors import problem_response

PUBLIC = frozenset(
    {
        ("GET", "/api/health"),
        ("HEAD", "/api/health"),
        ("POST", "/api/auth/login"),
        ("POST", "/api/auth/logout"),
    }
)


def cookie_value(cookie_header: str | None, name: str) -> str | None:
    if not cookie_header:
        return None
    jar: SimpleCookie = SimpleCookie()
    try:
        jar.load(cookie_header)
    except CookieError:
        return None
    morsel = jar.get(name)
    return morsel.value if morsel is not None else None


class SessionGateMiddleware:
    def __init__(self, app: ASGIApp, session_cookie: str) -> None:
        self.app = app
        self.session_cookie = session_cookie

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            path = scope["path"].rstrip("/") or "/"
            if (path == "/api" or path.startswith("/api/")) and (
                scope["method"],
                path,
            ) not in PUBLIC:
                headers = dict(scope["headers"])
                raw = headers.get(b"cookie")
                token = cookie_value(raw.decode("latin-1") if raw else None, self.session_cookie)
                if not looks_like_token(token):
                    await problem_response(
                        401,
                        code="not-authenticated",
                        title="Not signed in",
                        detail="Sign in to continue.",
                    )(scope, receive, send)
                    return
        await self.app(scope, receive, send)
