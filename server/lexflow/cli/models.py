"""Show whether local embeddings could run here, without changing anything.

    python -m lexflow.cli.models status

Prints the embeddings setting, the configured model and what is in the model
folder, and whether the database server offers the pgvector extension. It
downloads nothing, creates no folders and writes nothing to the database.

There is no download command yet: storing embeddings needs a database image
with pgvector, which has not been set up (``lexflow/embeddings.py``).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from lexflow.config import Settings, get_settings
from lexflow.db import engine_for
from lexflow.embeddings import EmbeddingsUnavailableError, provider_for


def _model_folder(folder: Path) -> str:
    if not folder.is_dir():
        return f"{folder} (does not exist; no model downloaded)"
    files = sum(1 for path in folder.rglob("*") if path.is_file())
    if files == 0:
        return f"{folder} (empty; no model downloaded)"
    return f"{folder} ({files} file{'' if files == 1 else 's'})"


def _pgvector(settings: Settings) -> tuple[str, bool]:
    """A description of pgvector on the database server, and whether it is usable."""
    engine = engine_for(settings.database_url)
    try:
        with engine.connect() as connection:
            available = connection.scalar(
                text("SELECT default_version FROM pg_available_extensions WHERE name = 'vector'")
            )
            installed = connection.scalar(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            )
    finally:
        engine.dispose()
    if installed:
        return f"installed in this database (version {installed})", True
    if available:
        return f"offered by the server (version {available}) but not installed", True
    return "not offered by this database server", False


def cmd_status(settings: Settings, out: TextIO) -> int:
    print(f"Embeddings:    {settings.embeddings} (LEXFLOW_EMBEDDINGS)", file=out)
    print(f"Model:         {settings.embedding_model}", file=out)
    print(f"Model folder:  {_model_folder(settings.model_dir)}", file=out)
    try:
        description, usable = _pgvector(settings)
    except DBAPIError:
        print("pgvector:      unknown (the database could not be reached)", file=out)
        return 1
    print(f"pgvector:      {description}", file=out)
    try:
        provider_for(settings)
    except EmbeddingsUnavailableError as exc:
        print(f"Worker:        will not start: {exc}", file=out)
        return 0
    if settings.embeddings == "disabled":
        print("Worker:        stores chunks without embeddings", file=out)
    if not usable:
        print(
            "Note:          local embeddings need a database image with pgvector "
            "(see docs/PHASE3_EXECUTION_LOG.md, P3-M5).",
            file=out,
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m lexflow.cli.models",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="show the embeddings setup (changes nothing)")
    return parser


def main(argv: Sequence[str] | None = None, *, out: TextIO = sys.stdout) -> int:
    build_parser().parse_args(argv)
    return cmd_status(get_settings(), out)


if __name__ == "__main__":
    raise SystemExit(main())
