"""Embed the judgments of the isolated demo database with the local model only.

    .venv\\Scripts\\python scripts/index_judgments_isolated.py
        [--database lexflow_e2e] [--confirm N]

Runs ``python -m lexflow.cli.judgments index`` against the named database
with ``LEXFLOW_EMBEDDINGS=local`` (the pinned BAAI/bge-small-en-v1.5 files in
``var/models``; nothing is downloaded and no text leaves this computer), after
the same checks as ``import_judgments_isolated.py``: an "e2e" database that
is not the DATABASE_URL (live) one, reporting that name and the isolated-demo
marker. Without ``--confirm N`` the CLI only lists what it would embed.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

SERVER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_ROOT))

from lexflow.config import Settings  # noqa: E402


def guards() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "lexflow_import_isolated", SERVER_ROOT / "scripts" / "import_judgments_isolated.py"
    )
    if spec is None or spec.loader is None:
        raise SystemExit("Cannot load the isolation checks.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database", default="lexflow_e2e")
    parser.add_argument("--confirm", type=int)
    args = parser.parse_args(argv)
    checks = guards()
    url = checks.isolated_url(args.database, Settings().database_url)
    checks.check_identity(url, args.database)
    print(f"Checks passed: database {args.database!r} is marked; local embeddings only.")
    command = [sys.executable, "-m", "lexflow.cli.judgments", "index"]
    if args.confirm is not None:
        command += ["--confirm", str(args.confirm)]
    env = {**os.environ, "DATABASE_URL": url, "LEXFLOW_EMBEDDINGS": "local"}
    # This interpreter and the CLI module; the only argument is an integer.
    return subprocess.run(command, cwd=SERVER_ROOT, env=env, check=False).returncode  # noqa: S603


if __name__ == "__main__":
    raise SystemExit(main())
