"""Protections for an API that has no authentication yet (Phase 1).

Binding to 127.0.0.1 keeps other machines out, but not web pages running in the
user's own browser:

- **DNS rebinding.** A page on ``evil.example`` can make its hostname resolve
  to 127.0.0.1 and then read the API as if it were same-origin. Requests whose
  ``Host`` is not a loopback name are refused (400 ``invalid-host``).
- **Cross-site requests (CSRF).** Any site can submit an HTML form to
  127.0.0.1, including a multipart upload, without a CORS preflight. Browsers
  send ``Origin`` with such requests, so state-changing requests from a
  non-loopback origin are refused (403 ``forbidden-origin``). Requests without
  ``Origin`` (curl, scripts, tests) are allowed.
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlsplit

from starlette.types import ASGIApp, Receive, Scope, Send

from lexflow.errors import problem_response

LOOPBACK_NAMES = frozenset({"localhost", "127.0.0.1", "::1"})
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def host_name(host_header: str) -> str:
    """'localhost:8000' -> 'localhost'; '[::1]:8000' -> '::1'."""
    host = host_header.strip().lower()
    if host.startswith("["):
        return host[1 : host.find("]")] if "]" in host else ""
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def origin_is_loopback(origin: str) -> bool:
    if origin == "null":  # sandboxed frames, file:// pages
        return False
    parts = urlsplit(origin)
    return parts.scheme in {"http", "https"} and (parts.hostname or "") in LOOPBACK_NAMES


class LocalOnlyMiddleware:
    def __init__(self, app: ASGIApp, allowed_hosts: Iterable[str]) -> None:
        self.app = app
        self.allowed_hosts = frozenset(h.lower() for h in allowed_hosts)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope["headers"]}
        if host_name(headers.get("host", "")) not in self.allowed_hosts:
            response = problem_response(
                400,
                code="invalid-host",
                detail="This API only answers requests addressed to this computer.",
            )
            await response(scope, receive, send)
            return

        origin = headers.get("origin")
        if (
            scope["method"] in UNSAFE_METHODS
            and origin is not None
            and not origin_is_loopback(origin)
        ):
            response = problem_response(
                403,
                code="forbidden-origin",
                detail="Changes are only accepted from LexFlow running on this computer.",
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
