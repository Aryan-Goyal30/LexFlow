"""Embeddings: off by default, and refused (not silently ignored) when asked for.

``LEXFLOW_EMBEDDINGS=local`` needs a database that can store vectors
(pgvector), which is not set up; see ``lexflow/embeddings.py``.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest

from lexflow import worker
from lexflow.cli import models
from lexflow.config import Settings, get_settings
from lexflow.embeddings import UNAVAILABLE, EmbeddingsUnavailableError, provider_for
from lexflow.storage import LocalDiskStorage


def settings(**changes: Any) -> Settings:
    return get_settings().model_copy(update=changes)


def test_embeddings_are_off_by_default() -> None:
    assert Settings().embeddings == "disabled"
    assert provider_for(settings()) is None


def test_local_embeddings_are_refused_with_the_reason() -> None:
    with pytest.raises(EmbeddingsUnavailableError) as raised:
        provider_for(settings(embeddings="local"))
    assert str(raised.value) == UNAVAILABLE
    assert "pgvector" in UNAVAILABLE and "LEXFLOW_EMBEDDINGS=disabled" in UNAVAILABLE


def test_the_worker_takes_no_job_when_embeddings_cannot_run(tmp_path: Path) -> None:
    def no_database() -> Any:
        raise AssertionError("the worker must not touch the queue")

    with pytest.raises(EmbeddingsUnavailableError):
        worker.run(
            no_database,
            LocalDiskStorage(tmp_path),
            settings(embeddings="local"),
            worker_id="test",
            once=True,
        )


def test_the_worker_command_says_why_it_will_not_start(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LEXFLOW_EMBEDDINGS", "local")
    get_settings.cache_clear()
    try:
        assert worker.main(["--once"]) == 2
    finally:
        get_settings.cache_clear()
    assert capsys.readouterr().err.strip() == UNAVAILABLE


# --- python -m lexflow.cli.models status ----------------------------------------------


def status(**changes: Any) -> tuple[int, str]:
    out = io.StringIO()
    code = models.cmd_status(settings(**changes), out)
    return code, out.getvalue()


def test_status_reports_the_setup_and_creates_nothing(tmp_path: Path) -> None:
    folder = tmp_path / "models"
    code, out = status(model_dir=folder)
    assert code == 0
    assert "Embeddings:    disabled" in out
    assert "Model:         BAAI/bge-small-en-v1.5" in out
    assert "does not exist; no model downloaded" in out
    assert "pgvector:" in out and "unknown" not in out  # the server was asked
    assert "Worker:        stores chunks without embeddings" in out
    assert not folder.exists()


def test_status_counts_what_is_in_the_model_folder(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    assert "(empty; no model downloaded)" in status(model_dir=tmp_path / "empty")[1]
    (tmp_path / "copy" / "onnx").mkdir(parents=True)
    (tmp_path / "copy" / "config.json").write_text("{}")
    (tmp_path / "copy" / "onnx" / "model.onnx").write_bytes(b"\0")
    assert "(2 files)" in status(model_dir=tmp_path / "copy")[1]


def test_status_shows_that_local_embeddings_would_be_refused(tmp_path: Path) -> None:
    code, out = status(embeddings="local", model_dir=tmp_path)
    assert code == 0
    assert f"Worker:        will not start: {UNAVAILABLE}" in out


def test_status_without_a_database(tmp_path: Path) -> None:
    code, out = status(
        database_url="postgresql+psycopg://nobody@127.0.0.1:1/none", model_dir=tmp_path
    )
    assert code == 1
    assert "unknown (the database could not be reached)" in out
    assert "nobody" not in out  # the database URL is never printed


def test_the_command_line_only_offers_status() -> None:
    with pytest.raises(SystemExit):
        models.build_parser().parse_args(["download"])
    assert models.build_parser().parse_args(["status"]).command == "status"
