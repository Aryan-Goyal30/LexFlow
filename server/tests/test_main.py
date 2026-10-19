"""Start-up rules of ``python -m lexflow``, and the test session's own settings.

Phase 1 has no authentication, so listening only on this computer is the main
protection: ``main()`` must refuse every other address before starting a server.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import uvicorn

import lexflow.__main__ as entry
from lexflow.config import SERVER_ROOT, get_settings


@pytest.fixture
def fresh_settings() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def server_starts(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Records uvicorn.run calls instead of starting a server."""
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: calls.append(kwargs))
    return calls


@pytest.mark.parametrize(
    "host",
    # S104: these all-interfaces addresses are the inputs the test proves are refused.
    ["0.0.0.0", "::", "192.168.1.20", "10.0.0.5", "lexflow.example", ""],  # noqa: S104
)
def test_refuses_to_listen_beyond_this_computer(
    host: str,
    monkeypatch: pytest.MonkeyPatch,
    fresh_settings: None,
    server_starts: list[dict[str, Any]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LEXFLOW_API_HOST", host)

    assert entry.main() == 2
    assert server_starts == []  # no server was started
    assert "Refusing to listen" in capsys.readouterr().err


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
def test_listens_on_loopback_addresses(
    host: str,
    monkeypatch: pytest.MonkeyPatch,
    fresh_settings: None,
    server_starts: list[dict[str, Any]],
) -> None:
    monkeypatch.setenv("LEXFLOW_API_HOST", host)

    assert entry.main() == 0
    assert len(server_starts) == 1
    assert server_starts[0]["host"] == host


def test_tests_never_use_the_development_upload_folder(fresh_settings: None) -> None:
    upload_dir = get_settings().upload_dir.resolve()

    assert upload_dir == Path(os.environ["LEXFLOW_UPLOAD_DIR"]).resolve()
    assert not upload_dir.is_relative_to((SERVER_ROOT / "var").resolve())
