"""The local embedding model: download it explicitly, check it, queue indexing.

    python -m lexflow.cli.models status                      # changes nothing
    python -m lexflow.cli.models download                    # shows what would be downloaded
    python -m lexflow.cli.models download --confirm          # downloads and verifies it
    python -m lexflow.cli.models verify                      # loads it and embeds a test sentence
    python -m lexflow.cli.models queue-indexing              # shows what would be queued
    python -m lexflow.cli.models queue-indexing --confirm N  # queues N documents for indexing

``download`` is the only way LexFlow fetches a model. It fetches the files of
``BAAI/bge-small-en-v1.5`` pinned to one revision from huggingface.co (about
134 MB), writes each to a ``.part`` file, checks its size and SHA-256 and only
then moves it into place, so an interrupted or altered download is never used.
It is recorded in the audit log. Nothing else downloads: the worker and the API
only read these files.

``queue-indexing`` marks extracted documents whose chunks have no vectors for
the current model (never indexed, failed, or indexed with another model) as
waiting for the worker. It previews first; ``--confirm N`` must match the
number listed. It changes no document, text or chunk.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import sys
import time
import urllib.request
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import BinaryIO, TextIO

from sqlalchemy import Select, func, or_, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from lexflow.audit import Actor, AuditLog
from lexflow.config import Settings, get_settings
from lexflow.db import engine_for, get_independent_sessions
from lexflow.embeddings import (
    DIMENSIONS,
    MANIFEST,
    MODEL_KEY,
    MODEL_NAME,
    MODEL_REVISION,
    SOURCE_URL,
    EmbeddingsUnavailableError,
    LocalBgeProvider,
    ModelFile,
    check_files,
    model_path,
    sha256_of,
)
from lexflow.models import Case, Document, DocumentChunkEmbedding, DocumentExtraction

Fetch = Callable[[str], BinaryIO]
DB_MESSAGE = (
    "The database could not be used: is it running, and are the migrations applied "
    "(alembic upgrade head)?"
)


class CommandError(Exception):
    """A problem to report to the operator (exit status 1)."""


def _megabytes(size: int) -> str:
    return f"{size / 1_000_000:.1f} MB"


def _fetch(url: str) -> BinaryIO:
    request = urllib.request.Request(url, headers={"User-Agent": "LexFlow model download"})  # noqa: S310 - fixed https URL
    return urllib.request.urlopen(request, timeout=60)  # type: ignore[no-any-return]  # noqa: S310


# --- download ---------------------------------------------------------------------------


def _download_file(url: str, target: Path, size: int, sha256: str, fetch: Fetch) -> None:
    part = target.with_name(target.name + ".part")
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    written = 0
    try:
        with fetch(url) as response, part.open("wb") as out:
            while block := response.read(1 << 20):
                written += len(block)
                if written > size:
                    raise CommandError(f"{target.name}: larger than expected; download stopped.")
                digest.update(block)
                out.write(block)
        if written != size:
            raise CommandError(f"{target.name}: got {written} bytes, expected {size}.")
        if digest.hexdigest() != sha256:
            raise CommandError(f"{target.name}: SHA-256 does not match the pinned value.")
        part.replace(target)
    except OSError as exc:
        raise CommandError(f"{target.name}: download failed ({exc}).") from exc
    finally:
        part.unlink(missing_ok=True)


def cmd_download(
    args: argparse.Namespace, settings: Settings, out: TextIO, *, fetch: Fetch, audit: AuditLog
) -> int:
    root = model_path(settings)
    total = sum(f.size for f in MANIFEST)
    print(f"Model:       {MODEL_NAME} (revision {MODEL_REVISION})", file=out)
    print("Source:      huggingface.co (files pinned by SHA-256)", file=out)
    print(f"Destination: {root}", file=out)
    pending = [f for f in MANIFEST if not _present(root, f)]
    for f in MANIFEST:
        state = "to download" if f in pending else "present and verified"
        print(f"  {f.path:24} {_megabytes(f.size):>9}  {state}", file=out)
    if not pending:
        print("The model is already downloaded and verified.", file=out)
        return 0
    if not args.confirm:
        size = sum(f.size for f in pending)
        print(
            f"Preview only: nothing was downloaded. To download {_megabytes(size)} "
            f"(model total {_megabytes(total)}), run the same command with --confirm.",
            file=out,
        )
        return 0
    for f in pending:
        url = SOURCE_URL.format(name=MODEL_NAME, revision=MODEL_REVISION, path=f.path)
        started = time.monotonic()
        print(f"Downloading {f.path} ...", file=out, flush=True)
        _download_file(url, root / f.path, f.size, f.sha256, fetch)
        print(f"  verified ({time.monotonic() - started:.0f} s)", file=out)
    if problems := check_files(root):
        raise CommandError("After download: " + "; ".join(problems))
    audit.record(
        "model.downloaded",
        actor=Actor.command_line(getpass.getuser()),
        target_type="model",
        details={"model": MODEL_NAME, "revision": MODEL_REVISION},
    )
    print("Done. Check it with: python -m lexflow.cli.models verify", file=out)
    return 0


def _present(root: Path, item: ModelFile) -> bool:
    """Whether this manifest file is already in place and intact."""
    path = root / item.path
    return path.is_file() and path.stat().st_size == item.size and sha256_of(path) == item.sha256


# --- verify -------------------------------------------------------------------------------


def cmd_verify(settings: Settings, out: TextIO) -> int:
    root = model_path(settings)
    started = time.monotonic()
    try:
        provider = LocalBgeProvider(
            root, threads=settings.embedding_threads, batch_size=settings.embedding_batch_size
        )
    except EmbeddingsUnavailableError as exc:
        raise CommandError(str(exc)) from exc
    loaded = time.monotonic() - started
    sentences = [
        "FICTIONAL: the tenant failed to pay rent for six months.",
        "FICTIONAL: rent arrears accumulated over half a year.",
        "FICTIONAL: the trademark was registered in class 30.",
    ]
    started = time.monotonic()
    vectors = provider.embed_passages(sentences)
    took = time.monotonic() - started
    norms = [sum(x * x for x in v) ** 0.5 for v in vectors]

    def cosine(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))

    related, unrelated = cosine(vectors[0], vectors[1]), cosine(vectors[0], vectors[2])
    print(f"Model:      {MODEL_KEY} (files verified, loaded in {loaded:.1f} s)", file=out)
    print(f"Embedding:  {len(vectors)} sentences in {took:.2f} s on the CPU", file=out)
    print(f"Dimensions: {len(vectors[0])} (expected {DIMENSIONS})", file=out)
    print(f"Lengths:    {', '.join(f'{n:.4f}' for n in norms)} (expected 1.0000)", file=out)
    print(f"Similarity: related {related:.3f}, unrelated {unrelated:.3f}", file=out)
    ok = (
        all(len(v) == DIMENSIONS for v in vectors)
        and all(abs(n - 1) < 1e-3 for n in norms)
        and related > unrelated
    )
    print("Verified." if ok else "Verification FAILED.", file=out)
    return 0 if ok else 1


# --- status -------------------------------------------------------------------------------


def _model_folder(root: Path) -> str:
    if not root.is_dir():
        return f"{root} (not downloaded)"
    problems = check_files(root)
    return f"{root} ({'verified' if not problems else '; '.join(problems)})"


def cmd_status(settings: Settings, out: TextIO) -> int:
    print(f"Embeddings:    {settings.embeddings} (LEXFLOW_EMBEDDINGS)", file=out)
    print(f"Model:         {MODEL_KEY}", file=out)
    print(f"Model files:   {_model_folder(model_path(settings))}", file=out)
    engine = engine_for(settings.database_url)
    try:
        with engine.connect() as connection:
            available = connection.scalar(
                text("SELECT default_version FROM pg_available_extensions WHERE name = 'vector'")
            )
            installed = connection.scalar(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            )
            table = connection.scalar(text("SELECT to_regclass('document_chunk_embeddings')"))
            counts: dict[str, int] = {}
            if table is not None:
                for status, count in connection.execute(
                    select(DocumentExtraction.index_status, func.count())
                    .where(DocumentExtraction.status == "ready")
                    .group_by(DocumentExtraction.index_status)
                ):
                    counts[status] = count
            vectors = (
                connection.scalar(
                    select(func.count())
                    .select_from(DocumentChunkEmbedding)
                    .where(DocumentChunkEmbedding.model == MODEL_KEY)
                )
                if table is not None
                else 0
            )
    except DBAPIError:
        print("pgvector:      unknown (the database could not be reached)", file=out)
        return 1
    finally:
        engine.dispose()
    if installed:
        pgvector = f"installed (version {installed})"
    elif available:
        pgvector = f"offered by the server (version {available}) but not installed"
    else:
        pgvector = "not offered by this database server"
    print(f"pgvector:      {pgvector}", file=out)
    if table is None:
        print("Vectors table: missing (apply migration 0009: alembic upgrade head)", file=out)
        return 0
    summary = ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "none"
    print(f"Documents:     extracted documents by index status: {summary}", file=out)
    print(f"Vectors:       {vectors} for {MODEL_KEY}", file=out)
    return 0


# --- queue-indexing -------------------------------------------------------------------------


def _needs_indexing(
    case_number: str | None,
) -> Select[tuple[DocumentExtraction, Document, Case]]:
    query = (
        select(DocumentExtraction, Document, Case)
        .join(Document, Document.id == DocumentExtraction.document_id)
        .join(Case, Case.id == Document.case_id)
        .where(
            DocumentExtraction.status == "ready",
            or_(
                DocumentExtraction.index_status.in_(("disabled", "failed")),
                (DocumentExtraction.index_status == "indexed")
                & (DocumentExtraction.embedding_model != MODEL_KEY),
            ),
        )
        .order_by(Case.case_number, Document.id)
    )
    if case_number:
        query = query.where(Case.case_number == case_number.strip())
    return query


def cmd_queue_indexing(
    args: argparse.Namespace,
    settings: Settings,
    session: Session,
    out: TextIO,
    *,
    audit: AuditLog,
) -> int:
    if session.scalar(text("SELECT to_regclass('document_chunk_embeddings')")) is None:
        raise CommandError("Apply migration 0009 first (alembic upgrade head).")
    rows = session.execute(_needs_indexing(args.case)).tuples().all()
    if not rows:
        print("Every extracted document is indexed (or waiting) for the current model.", file=out)
        return 0
    lines = [f"{'CASE':14} {'NOW':9} {'ID':36}  NAME"]
    lines += [
        f"{case.case_number:14} {job.index_status:9} {document.id!s:36}  {document.name}"
        for job, document, case in rows
    ]
    print("\n".join(lines), file=out)
    if args.confirm is None:
        print(
            f"Preview only: nothing was changed. To queue these {len(rows)} document(s) for "
            f"indexing, run the same command with --confirm {len(rows)}.",
            file=out,
        )
        return 0
    if args.confirm != len(rows):
        raise CommandError(
            f"--confirm {args.confirm} does not match the {len(rows)} document(s) listed; "
            "nothing was queued. Check the preview again."
        )
    queued: list[tuple[uuid.UUID, uuid.UUID, str, str]] = []
    for job, document, case in rows:
        result = session.execute(
            update(DocumentExtraction)
            .where(
                DocumentExtraction.document_id == job.document_id,
                DocumentExtraction.status == "ready",
                DocumentExtraction.index_status == job.index_status,
            )
            .values(index_status="pending", index_reason=None)
        )
        if result.rowcount:  # type: ignore[attr-defined]
            queued.append((document.id, case.id, case.case_number, job.index_status))
    session.commit()
    actor = Actor.command_line(getpass.getuser())
    for document_id, case_id, case_number, previous in queued:
        audit.record(
            "document.indexing_queued",
            actor=actor,
            target_type="document",
            target_id=document_id,
            case_id=case_id,
            details={"caseNumber": case_number, "previousStatus": previous},
        )
    print(f"Queued {len(queued)} document(s) for indexing.", file=out)
    if settings.embeddings != "local":
        print(
            "Embeddings are disabled (LEXFLOW_EMBEDDINGS), so the worker will index them "
            "only once they are enabled.",
            file=out,
        )
    return 0


# --- entry point --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m lexflow.cli.models",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="show the embeddings setup (changes nothing)")
    download = commands.add_parser("download", help="download the pinned model (preview first)")
    download.add_argument("--confirm", action="store_true", help="go ahead and download")
    commands.add_parser("verify", help="load the model and embed a test sentence")
    queue = commands.add_parser(
        "queue-indexing", help="queue extracted documents for indexing (preview first)"
    )
    queue.add_argument("--case", help="only this case number")
    queue.add_argument(
        "--confirm",
        type=int,
        metavar="N",
        help="go ahead; N must equal the number of documents the preview listed",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    out: TextIO = sys.stdout,
    fetch: Fetch = _fetch,
) -> int:
    args = build_parser().parse_args(argv)
    settings = get_settings()
    try:
        if args.command == "status":
            return cmd_status(settings, out)
        if args.command == "verify":
            return cmd_verify(settings, out)
        engine = engine_for(settings.database_url)
        audit = AuditLog(get_independent_sessions(engine))
        if args.command == "download":
            return cmd_download(args, settings, out, fetch=fetch, audit=audit)
        with Session(engine, expire_on_commit=False) as session:
            return cmd_queue_indexing(args, settings, session, out, audit=audit)
    except CommandError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except DBAPIError:
        print(DB_MESSAGE, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
