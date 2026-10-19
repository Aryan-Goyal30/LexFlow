"""Run an extraction in a separate process that can be stopped.

A damaged or hostile file can make a parser loop, recurse deeply or use a lot
of memory. The worker therefore extracts in a child process ("spawn", which
works the same on Windows, macOS and Linux) and kills it when the time limit
passes. The child returns only the extracted sections or an error code and
message; nothing else crosses back.
"""

from __future__ import annotations

import multiprocessing
from collections.abc import Callable
from multiprocessing.connection import Connection

from lexflow.extraction import Extracted, ExtractionError, Limits, Section, extract

Extract = Callable[[str, bytes, Limits], Extracted]


def _child(
    conn: Connection, target: Extract, content_type: str, data: bytes, limits: Limits
) -> None:
    try:
        result = target(content_type, data, limits)
        conn.send(
            (
                "ok",
                [(s.page_number, s.text) for s in result.sections],
                result.extractor,
                result.page_count,
            )
        )
    except ExtractionError as error:
        conn.send(("error", error.code, error.message, error.retry))
    except Exception:  # an extractor bug: reported without details
        conn.send(("error", "extractor-error", "The text could not be extracted.", False))
    finally:
        conn.close()


def run_extraction(
    content_type: str,
    data: bytes,
    limits: Limits,
    *,
    timeout_seconds: float,
    target: Extract = extract,
) -> Extracted:
    """Extract in a child process; ``ExtractionError`` on failure or timeout.

    ``target`` must be a module-level function (it is imported by the child).
    """
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(
        target=_child, args=(sender, target, content_type, data, limits), daemon=True
    )
    process.start()
    sender.close()  # the child holds the only sending end now
    try:
        if not receiver.poll(timeout_seconds):
            raise ExtractionError(
                "timed-out",
                f"Extraction took longer than {timeout_seconds:g} seconds and was stopped.",
            )
        try:
            message = receiver.recv()
        except EOFError:  # the child died without answering (crash, memory)
            raise ExtractionError(
                "extractor-crashed",
                "The text extraction stopped unexpectedly.",
                retry=True,
            ) from None
    finally:
        receiver.close()
        if process.is_alive():
            process.kill()
        process.join(timeout=10)

    if message[0] == "ok":
        _, sections, extractor, page_count = message
        return Extracted(
            sections=[Section(page_number=p, text=t) for p, t in sections],
            extractor=extractor,
            page_count=page_count,
        )
    _, code, text, retry = message
    raise ExtractionError(code, text, retry)
