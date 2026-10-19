"""Request checks that run before any route: where a request may come from.

The API listens on 127.0.0.1 only, but web pages in the user's own browser can
still reach it:

- **DNS rebinding.** A page on ``evil.example`` can make its hostname resolve
  to 127.0.0.1 and then read the API as if it were same-origin. Requests whose
  ``Host`` is not a loopback name are refused (400 ``invalid-host``).
- **Cross-site request forgery.** Sign-in uses a cookie, which the browser
  attaches to any request to the API's site. ``SameSite=Strict`` does not help
  between ports of ``localhost`` (they are the same site), so state-changing
  requests (POST/PUT/PATCH/DELETE) must:

  1. carry ``X-LexFlow-Request: 1``. A cross-origin page cannot add a custom
     header without a CORS preflight, and nothing grants one (the API has no
     CORS, and the Vite proxy's CORS is turned off): 403 ``csrf-header-missing``;
  2. come from an allowed origin, compared exactly (scheme, host and port), when
     the browser names one: 403 ``forbidden-origin``;
  3. name an origin at all if they carry the session cookie, since every browser
     sends ``Origin`` on such requests: 403 ``origin-required``.

  Scripts and tests without a session (no ``Origin``, no cookie) only need the
  header.
"""

from __future__ import annotations

from collections.abc import Iterable
from http.cookies import CookieError, SimpleCookie

from starlette.types import ASGIApp, Receive, Scope, Send

from lexflow.errors import problem_response

LOOPBACK_NAMES = frozenset({"localhost", "127.0.0.1", "::1"})
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
REQUEST_HEADER = "x-lexflow-request"


def host_name(host_header: str) -> str:
    """'localhost:8000' -> 'localhost'; '[::1]:8000' -> '::1'."""
    host = host_header.strip().lower()
    if host.startswith("["):
        return host[1 : host.find("]")] if "]" in host else ""
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def normalise_origin(origin: str) -> str:
    return origin.strip().rstrip("/").lower()


def has_cookie(cookie_header: str | None, name: str) -> bool:
    if not cookie_header:
        return False
    jar: SimpleCookie = SimpleCookie()
    try:
        jar.load(cookie_header)
    except CookieError:
        return True  # unparseable: assume the worst
    return name in jar


class LocalOnlyMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        allowed_hosts: Iterable[str],
        allowed_origins: Iterable[str],
        session_cookie: str,
    ) -> None:
        self.app = app
        self.allowed_hosts = frozenset(h.lower() for h in allowed_hosts)
        self.allowed_origins = frozenset(normalise_origin(o) for o in allowed_origins)
        self.session_cookie = session_cookie

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope["headers"]}
        if host_name(headers.get("host", "")) not in self.allowed_hosts:
            await problem_response(
                400,
                code="invalid-host",
                detail="This API only answers requests addressed to this computer.",
            )(scope, receive, send)
            return

        if scope["method"] in UNSAFE_METHODS:
            refusal = self._refuse_change(headers)
            if refusal is not None:
                code, detail = refusal
                await problem_response(403, code=code, detail=detail)(scope, receive, send)
                return

        await self.app(scope, receive, send)

    def _refuse_change(self, headers: dict[str, str]) -> tuple[str, str] | None:
        if headers.get(REQUEST_HEADER) != "1":
            return (
                "csrf-header-missing",
                "This request did not come from the LexFlow app and was refused.",
            )
        origin = headers.get("origin")
        if origin is not None:
            if normalise_origin(origin) not in self.allowed_origins:
                return (
                    "forbidden-origin",
                    "Changes are only accepted from LexFlow running on this computer.",
                )
        elif has_cookie(headers.get("cookie"), self.session_cookie):
            return (
                "origin-required",
                "This request did not say where it came from and was refused.",
            )
        return None
