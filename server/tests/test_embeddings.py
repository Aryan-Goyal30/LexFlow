"""The local embedding model: off by default, explicit download, honest checks.

Tests marked ``needs_model`` use the real ``BAAI/bge-small-en-v1.5`` files and
are skipped until they are downloaded (``python -m lexflow.cli.models download
--confirm``). Everything else runs without the model and without the network:
downloads are tested with a fake fetcher and a tiny manifest.
"""

from __future__ import annotations

import hashlib
import io
import uuid
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from lexflow import embeddings, worker
from lexflow.audit import AuditLog
from lexflow.cli import models
from lexflow.config import Settings, get_settings
from lexflow.db import get_independent_sessions
from lexflow.embeddings import (
    DIMENSIONS,
    MODEL_KEY,
    EmbeddingsUnavailableError,
    ModelFile,
    check_database,
    check_files,
    model_path,
    provider_for,
)
from lexflow.models import AuditEvent, DocumentExtraction
from lexflow.seed import sample_uuid
from lexflow.seed.loader import load_sample_data
from lexflow.storage import LocalDiskStorage
from tests.embedding_fakes import make_ready

SATTVIK = sample_uuid("case", "case-1005")
REAL_MODEL = model_path(get_settings())
needs_model = pytest.mark.skipif(
    bool(check_files(REAL_MODEL)), reason="the embedding model is not downloaded"
)


def settings(**changes: Any) -> Settings:
    return get_settings().model_copy(update=changes)


# --- switching it on ------------------------------------------------------------------------


def test_embeddings_are_off_by_default() -> None:
    assert Settings().embeddings == "disabled"
    assert provider_for(settings()) is None


def test_local_embeddings_need_the_downloaded_model(tmp_path: Path) -> None:
    with pytest.raises(EmbeddingsUnavailableError) as raised:
        provider_for(settings(embeddings="local", model_dir=tmp_path))
    message = str(raised.value)
    assert "onnx/model.onnx is missing" in message
    assert "python -m lexflow.cli.models download --confirm" in message
    assert not any(tmp_path.iterdir())  # nothing was downloaded or created


def test_only_the_pinned_model_is_accepted(tmp_path: Path) -> None:
    with pytest.raises(EmbeddingsUnavailableError, match=r"Only BAAI/bge-small-en-v1\.5"):
        provider_for(settings(embeddings="local", embedding_model="other/model"))


def test_the_worker_takes_no_job_when_the_model_is_missing(tmp_path: Path) -> None:
    def no_database() -> Any:
        raise AssertionError("the worker must not touch the queue")

    with pytest.raises(EmbeddingsUnavailableError):
        worker.run(
            no_database,
            LocalDiskStorage(tmp_path),
            settings(embeddings="local", model_dir=tmp_path),
            worker_id="test",
            once=True,
        )


def test_the_worker_command_says_why_it_will_not_start(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setenv("LEXFLOW_EMBEDDINGS", "local")
    monkeypatch.setenv("LEXFLOW_MODEL_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        assert worker.main(["--once"]) == 2
    finally:
        get_settings.cache_clear()
    assert "models download --confirm" in capsys.readouterr().err


def test_a_database_without_the_vectors_table_is_refused(db: Session) -> None:
    check_database(db)  # migration 0009 is applied in the test database
    db.execute(text("DROP TABLE document_chunk_embeddings"))  # rolled back after the test
    with pytest.raises(EmbeddingsUnavailableError, match="migration 0009"):
        check_database(db)


# --- the model files ------------------------------------------------------------------------

FILES = {"onnx/model.onnx": b"pretend model", "tokenizer.json": b"{}"}


@pytest.fixture
def tiny_manifest(monkeypatch: pytest.MonkeyPatch) -> dict[str, bytes]:
    manifest = tuple(
        ModelFile(path, len(data), hashlib.sha256(data).hexdigest()) for path, data in FILES.items()
    )
    monkeypatch.setattr(embeddings, "MANIFEST", manifest)
    monkeypatch.setattr(models, "MANIFEST", manifest)
    return FILES


def test_damaged_or_partial_files_are_reported(
    tmp_path: Path, tiny_manifest: dict[str, bytes]
) -> None:
    assert check_files(tmp_path) == [f"{p} is missing" for p in FILES]
    (tmp_path / "onnx").mkdir()
    (tmp_path / "onnx" / "model.onnx").write_bytes(b"pretend")  # cut short
    (tmp_path / "tokenizer.json").write_bytes(b"[]")  # same size, other bytes
    assert check_files(tmp_path) == [
        "onnx/model.onnx has the wrong size (an interrupted download?)",
        "tokenizer.json does not match its SHA-256",
    ]


class Fetcher:
    """Serves the tiny manifest's files; records requested URLs."""

    def __init__(self, files: dict[str, bytes], *, tamper: str | None = None) -> None:
        self.files, self.tamper = files, tamper
        self.urls: list[str] = []

    def __call__(self, url: str) -> Any:
        self.urls.append(url)
        path = url.split(f"/resolve/{embeddings.MODEL_REVISION}/", 1)[1]
        data = self.files[path]
        if path == self.tamper:
            data = bytes(reversed(data))
        return io.BytesIO(data)


def download(engine: Engine, root: Path, fetch: Fetcher, *argv: str) -> tuple[int, str]:
    out = io.StringIO()
    args = models.build_parser().parse_args(["download", *argv])
    code = models.cmd_download(
        args,
        settings(model_dir=root),
        out,
        fetch=fetch,
        audit=AuditLog(get_independent_sessions(engine)),
    )
    return code, out.getvalue()


def test_download_previews_first_and_fetches_nothing(
    committed_engine: Engine, tmp_path: Path, tiny_manifest: dict[str, bytes]
) -> None:
    fetch = Fetcher(tiny_manifest)
    code, out = download(committed_engine, tmp_path, fetch)
    assert code == 0 and fetch.urls == []
    assert "Preview only: nothing was downloaded" in out and "--confirm" in out
    assert not any(tmp_path.iterdir())


def test_download_fetches_the_pinned_files_and_verifies_them(
    committed_engine: Engine, tmp_path: Path, tiny_manifest: dict[str, bytes]
) -> None:
    fetch = Fetcher(tiny_manifest)
    code, out = download(committed_engine, tmp_path, fetch, "--confirm")
    assert code == 0, out
    root = model_path(settings(model_dir=tmp_path))
    assert check_files(root) == []
    assert fetch.urls == [
        f"https://huggingface.co/BAAI/bge-small-en-v1.5/resolve/{embeddings.MODEL_REVISION}/{p}"
        for p in FILES
    ]
    with Session(committed_engine) as session:
        event = session.scalars(
            select(AuditEvent).where(AuditEvent.action == "model.downloaded")
        ).one()
    assert event.details == {"model": embeddings.MODEL_NAME, "revision": embeddings.MODEL_REVISION}
    again = Fetcher(tiny_manifest)
    assert (
        "already downloaded and verified"
        in download(committed_engine, tmp_path, again, "--confirm")[1]
    )
    assert again.urls == []


def test_a_download_that_does_not_match_is_refused_and_removed(
    committed_engine: Engine, tmp_path: Path, tiny_manifest: dict[str, bytes]
) -> None:
    fetch = Fetcher(tiny_manifest, tamper="tokenizer.json")
    with pytest.raises(models.CommandError, match="SHA-256 does not match"):
        download(committed_engine, tmp_path, fetch, "--confirm")
    root = model_path(settings(model_dir=tmp_path))
    assert not (root / "tokenizer.json").exists()
    assert not list(root.rglob("*.part"))


def test_an_interrupted_download_leaves_nothing_usable(
    committed_engine: Engine, tmp_path: Path, tiny_manifest: dict[str, bytes]
) -> None:
    class Broken(Fetcher):
        def __call__(self, url: str) -> Any:
            raise OSError("connection reset")

    with pytest.raises(models.CommandError, match="download failed"):
        download(committed_engine, tmp_path, Broken(tiny_manifest), "--confirm")
    assert check_files(model_path(settings(model_dir=tmp_path)))  # still not ready


# --- status ---------------------------------------------------------------------------------


def status(**changes: Any) -> tuple[int, str]:
    out = io.StringIO()
    code = models.cmd_status(settings(**changes), out)
    return code, out.getvalue()


def test_status_reports_the_setup_and_creates_nothing(tmp_path: Path) -> None:
    code, out = status(model_dir=tmp_path / "models")
    assert code == 0
    assert "Embeddings:    disabled" in out and f"Model:         {MODEL_KEY}" in out
    assert "(not downloaded)" in out
    assert "pgvector:      installed" in out  # the test database is at migration 0009
    assert "Documents:" in out and "Vectors:" in out
    assert not (tmp_path / "models").exists()


def test_status_without_a_database(tmp_path: Path) -> None:
    code, out = status(
        database_url="postgresql+psycopg://nobody@127.0.0.1:1/none", model_dir=tmp_path
    )
    assert code == 1 and "unknown (the database could not be reached)" in out
    assert "nobody" not in out


# --- queue-indexing -------------------------------------------------------------------------


def queue_indexing(engine: Engine, *argv: str) -> tuple[int, str]:
    out = io.StringIO()
    args = models.build_parser().parse_args(["queue-indexing", *argv])
    with Session(engine, expire_on_commit=False) as session:
        code = models.cmd_queue_indexing(
            args, settings(), session, out, audit=AuditLog(get_independent_sessions(engine))
        )
    return code, out.getvalue()


def index_status(engine: Engine, document_id: uuid.UUID) -> tuple[str, str | None]:
    with Session(engine) as session:
        job = session.get(DocumentExtraction, document_id)
        assert job is not None
        return job.index_status, job.embedding_model


def test_queue_indexing_previews_then_queues_what_lacks_current_vectors(
    committed_engine: Engine,
) -> None:
    with Session(committed_engine) as session:
        load_sample_data(session)
        session.commit()
        never = make_ready(session, SATTVIK, "Never.pdf", ["FICTIONAL."], index_status="disabled")
        stale = make_ready(session, SATTVIK, "Stale.pdf", ["FICTIONAL."], index_status="indexed")
        current = make_ready(
            session, SATTVIK, "Current.pdf", ["FICTIONAL."], index_status="indexed"
        )
        for document, model in ((stale, "old-model@1"), (current, MODEL_KEY)):
            job = session.get(DocumentExtraction, document)
            assert job is not None
            job.embedding_model = model
        session.commit()

    code, out = queue_indexing(committed_engine)
    assert code == 0 and "Preview only" in out and "--confirm 2" in out
    assert "Never.pdf" in out and "Stale.pdf" in out and "Current.pdf" not in out
    assert index_status(committed_engine, never) == ("disabled", None)

    with pytest.raises(models.CommandError, match="does not match"):
        queue_indexing(committed_engine, "--confirm", "3")
    code, out = queue_indexing(committed_engine, "--confirm", "2")
    assert code == 0 and "Queued 2 document(s)" in out and "Embeddings are disabled" in out
    assert index_status(committed_engine, never)[0] == "pending"
    assert index_status(committed_engine, stale)[0] == "pending"
    assert index_status(committed_engine, current) == ("indexed", MODEL_KEY)
    with Session(committed_engine) as session:
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.action == "document.indexing_queued")
        ).all()
    assert {e.target_id for e in events} == {never, stale}
    assert all((e.actor_name or "").startswith("command line (") for e in events)


def test_the_command_line_offers_these_commands() -> None:
    parser = models.build_parser()
    for command in ("status", "download", "verify", "queue-indexing"):
        assert parser.parse_args([command]).command == command
    with pytest.raises(SystemExit):
        parser.parse_args(["delete"])


# --- the real model (skipped until downloaded) ------------------------------------------------


@pytest.fixture(scope="module")
def real() -> embeddings.LocalBgeProvider:
    return embeddings.LocalBgeProvider(REAL_MODEL, threads=2, batch_size=8)


@needs_model
def test_the_real_model_gives_unit_vectors_of_384_dimensions(
    real: embeddings.LocalBgeProvider,
) -> None:
    vectors = real.embed_passages(["FICTIONAL: a short sentence.", "", "x " * 2000])
    assert [len(v) for v in vectors] == [DIMENSIONS] * 3  # empty and over-long texts too
    for vector in vectors:
        assert abs(sum(x * x for x in vector) - 1) < 1e-4


@needs_model
def test_the_real_model_is_deterministic_and_batch_independent(
    real: embeddings.LocalBgeProvider,
) -> None:
    texts = [f"FICTIONAL clause {n}: the lessee shall pay rent monthly." for n in range(11)]
    together = real.embed_passages(texts)
    alone = [real.embed_passages([t])[0] for t in texts[:3]]
    for a, b in zip(together[:3], alone, strict=True):
        assert max(abs(x - y) for x, y in zip(a, b, strict=True)) < 1e-4


@needs_model
def test_the_real_model_places_related_meanings_closer(real: embeddings.LocalBgeProvider) -> None:
    def cosine(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))

    query = real.embed_query("Did the tenant fall behind on rent?")
    related, unrelated = real.embed_passages(
        [
            "FICTIONAL: the lessee has not paid the monthly rent since March.",
            "FICTIONAL: the trademark was registered for biscuits in class 30.",
        ]
    )
    assert cosine(query, related) > cosine(query, unrelated) + 0.1
    assert real.embed_query("rent") != real.embed_passages(["rent"])[0]  # instruction applied


@needs_model
def test_verify_command_passes_with_the_real_model() -> None:
    out = io.StringIO()
    assert models.cmd_verify(get_settings(), out) == 0
    assert "Verified." in out.getvalue() and "Dimensions: 384" in out.getvalue()
