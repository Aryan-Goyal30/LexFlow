"""Stand-in extractors for the runner tests (test code only).

They run in the child process, so they must be importable module-level
functions. None of them produces document text.
"""

from __future__ import annotations

import os
import time

from lexflow.extraction import Extracted, Limits


def sleeps(content_type: str, data: bytes, limits: Limits) -> Extracted:
    time.sleep(60)
    raise AssertionError("should have been stopped")


def crashes(content_type: str, data: bytes, limits: Limits) -> Extracted:
    os._exit(3)


def has_a_bug(content_type: str, data: bytes, limits: Limits) -> Extracted:
    raise ValueError("internal detail that must not reach the user: " + data.decode())
