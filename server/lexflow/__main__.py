"""Start the API: ``python -m lexflow``.

Phase 1 has no authentication, so the server refuses to listen on anything but
a loopback address.
"""

from __future__ import annotations

import logging
import sys

import uvicorn

from lexflow.config import LOOPBACK_HOSTS, get_settings


def main() -> int:
    settings = get_settings()
    if settings.api_host not in LOOPBACK_HOSTS:
        print(
            f"Refusing to listen on {settings.api_host!r}: the Phase 1 API has no "
            "authentication and must stay on 127.0.0.1.",
            file=sys.stderr,
        )
        return 2
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    uvicorn.run(
        "lexflow.main:create_app",
        factory=True,
        host=settings.api_host,
        port=settings.api_port,
        access_log=False,  # lexflow.access logs requests instead
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
