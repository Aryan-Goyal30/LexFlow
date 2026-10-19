"""The document-processing worker (Phase 3).

    python -m lexflow.worker            # keep processing until stopped (Ctrl+C)
    python -m lexflow.worker --once     # process what is waiting, then exit

Runs beside the API, as a separate process. For each job it takes from the
queue (``lexflow.services.extraction_queue``): it reads the stored file and
checks it against the SHA-256 recorded at upload, extracts the text in a child
process that is stopped at the time limit, splits it into page-aware chunks
and stores the outcome. Failures are stored with their reason; nothing is ever
made up. Several workers may run at once: each job goes to one of them.

The worker never downloads models and never sends document text anywhere.
Its log names documents by id and outcome only, never their text.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import socket
import sys
import time
import uuid
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from lexflow.config import Settings, get_settings
from lexflow.db import engine_for
from lexflow.embeddings import EmbeddingsUnavailableError, provider_for
from lexflow.extraction import Extracted, ExtractionError, Limits
from lexflow.extraction.chunking import chunk_sections
from lexflow.extraction.runner import run_extraction
from lexflow.models import Document, DocumentExtraction
from lexflow.services import extraction_queue as queue
from lexflow.storage import LocalDiskStorage, Storage

logger = logging.getLogger("lexflow.worker")

Sessions = Callable[[], AbstractContextManager[Session]]
ExtractFn = Callable[[str, bytes, Limits, float], Extracted]


def default_extract(content_type: str, data: bytes, limits: Limits, timeout: float) -> Extracted:
    return run_extraction(content_type, data, limits, timeout_seconds=timeout)


def limits_from(settings: Settings) -> Limits:
    return Limits(
        max_pages=settings.extraction_max_pages,
        max_text_bytes=settings.extraction_max_text_bytes,
        max_unpacked_bytes=settings.extraction_max_unpacked_bytes,
    )


def new_worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


def _now() -> datetime:
    return datetime.now(UTC)


def _read(storage: Storage, document: Document) -> bytes | queue.Failure:
    key = document.storage_key
    if key is None:
        return queue.Failure("no-file", "This record has no stored file.")
    try:
        if not storage.exists(key):
            return queue.Failure("file-missing", "The stored file could not be found.")
        with storage.open(key) as handle:
            data = handle.read()
    except OSError:
        return queue.Failure(
            "storage-unavailable", "The stored file could not be read.", retry=True
        )
    if hashlib.sha256(data).hexdigest() != document.sha256:
        return queue.Failure(
            "file-changed", "The stored file no longer matches the file that was uploaded."
        )
    return data


def process(
    sessions: Sessions,
    storage: Storage,
    settings: Settings,
    document_id: uuid.UUID,
    worker_id: str,
    *,
    extract: ExtractFn = default_extract,
    now: Callable[[], datetime] = _now,
) -> str:
    """Process one claimed job; returns its new status (or ``"discarded"``)."""
    with sessions() as session:
        document = session.get(Document, document_id)
        if document is not None:
            session.expunge(document)
    if document is None:  # purged while waiting; its job went with it
        return "discarded"

    outcome: queue.Success | queue.Failure
    data = _read(storage, document)
    if isinstance(data, queue.Failure):
        outcome = data
    else:
        try:
            extracted = extract(
                document.content_type or "",
                data,
                limits_from(settings),
                settings.extraction_timeout_seconds,
            )
            outcome = queue.Success(
                sections=extracted.sections,
                chunks=chunk_sections(
                    extracted.sections, settings.chunk_size, settings.chunk_overlap
                ),
                extractor=extracted.extractor,
                page_count=extracted.page_count,
            )
        except ExtractionError as error:
            outcome = queue.Failure(error.code, error.message, error.retry)

    with sessions() as session:
        status = queue.complete(
            session,
            document_id,
            worker_id=worker_id,
            outcome=outcome,
            now=now(),
            max_attempts=settings.worker_max_attempts,
        )
    if isinstance(outcome, queue.Failure):
        logger.info("document %s: %s (%s)", document_id, status, outcome.code)
    else:
        logger.info(
            "document %s: %s (%d sections, %d chunks)",
            document_id,
            status,
            len(outcome.sections),
            len(outcome.chunks),
        )
    return status


def release(sessions: Sessions, document_id: uuid.UUID, worker_id: str) -> None:
    """Hand an interrupted job back to the queue (if this worker still holds it)."""
    with sessions() as session:
        session.execute(
            update(DocumentExtraction)
            .where(
                DocumentExtraction.document_id == document_id,
                DocumentExtraction.status == "processing",
                DocumentExtraction.worker_id == worker_id,
            )
            .values(status="queued", lease_expires_at=None, worker_id=None)
        )
        session.commit()


def run(
    sessions: Sessions,
    storage: Storage,
    settings: Settings,
    *,
    worker_id: str,
    once: bool,
    extract: ExtractFn = default_extract,
    now: Callable[[], datetime] = _now,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Claim and process jobs. With ``once``, stop when nothing is waiting.
    Returns how many jobs were processed. Raises ``EmbeddingsUnavailableError`` before
    claiming anything when the configured embeddings cannot be produced."""
    provider_for(settings)  # chunks are stored with index status "disabled"
    processed = 0
    while True:
        with sessions() as session:
            document_id = queue.claim(
                session,
                worker_id=worker_id,
                now=now(),
                lease_seconds=settings.worker_lease_seconds,
                max_attempts=settings.worker_max_attempts,
            )
        if document_id is None:
            if once:
                return processed
            sleep(settings.worker_poll_seconds)
            continue
        try:
            process(sessions, storage, settings, document_id, worker_id, extract=extract, now=now)
        except BaseException:
            release(sessions, document_id, worker_id)
            raise
        processed += 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m lexflow.worker", description=__doc__)
    parser.add_argument("--once", action="store_true", help="process what is waiting, then exit")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    factory = sessionmaker(bind=engine_for(settings.database_url), expire_on_commit=False)
    storage = LocalDiskStorage(settings.upload_dir)
    worker_id = new_worker_id()
    logger.info(
        "worker %s started (embeddings: %s, timeout %ss)",
        worker_id,
        settings.embeddings,
        settings.extraction_timeout_seconds,
    )
    try:
        count = run(factory, storage, settings, worker_id=worker_id, once=args.once)
    except KeyboardInterrupt:
        logger.info("worker %s stopped", worker_id)
        return 0
    except EmbeddingsUnavailableError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except DBAPIError:
        print(
            "The database could not be used: is it running, and are the migrations "
            "applied (alembic upgrade head)?",
            file=sys.stderr,
        )
        return 1
    logger.info("worker %s finished: %d document(s) processed", worker_id, count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
