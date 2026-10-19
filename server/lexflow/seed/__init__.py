"""Fictional sample data: stable ids and a repeat-safe loader.

Load it with ``python -m lexflow.seed`` (development only).
"""

from __future__ import annotations

import uuid

# Fixed namespace so every sample record always gets the same UUID.
SAMPLE_NAMESPACE = uuid.UUID("7f27cbaa-4c8e-4a53-a1bc-1d3f2536f8a0")


def sample_uuid(kind: str, key: str) -> uuid.UUID:
    """Deterministic UUID for a sample record, e.g. ``sample_uuid("case", "case-1005")``."""
    return uuid.uuid5(SAMPLE_NAMESPACE, f"{kind}:{key}")
