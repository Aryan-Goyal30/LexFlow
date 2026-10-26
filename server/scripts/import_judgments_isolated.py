"""Import an approved judgment manifest into the isolated demo database only.

    .venv\\Scripts\\python scripts/import_judgments_isolated.py MANIFEST
        --expect-manifest-sha256 HEX --database lexflow_e2e [--confirm N]

Runs ``python -m lexflow.cli.judgments import`` against the named database,
after these checks, in order (any failure stops before the import starts):

1. the manifest's SHA-256 equals the approved one (the exact previewed file);
2. the database is named here, never taken from DATABASE_URL: it must have
   "e2e" as a name part, must not be the DATABASE_URL (live) database, and a
   ``dbname``/``service`` URL parameter is refused;
3. the connection reports that name (``current_database()``) and the
   database carries the isolated-demo marker.

The database URL reaches the CLI only in the child's environment, never on a
command line or in output. Without ``--confirm N`` the CLI only previews.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, make_url, text

SERVER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_ROOT))

from lexflow.config import Settings  # noqa: E402
from lexflow.demo import DEMO_MARKER  # noqa: E402


def isolated_url(name: str, configured: str) -> str:
    base = make_url(configured)
    if {"dbname", "service"} & set(base.query):
        raise SystemExit("Refusing a DATABASE_URL with a dbname or service parameter.")
    parts = [p for p in "".join(c if c.isalnum() else " " for c in name.lower()).split()]
    if "e2e" not in parts:
        raise SystemExit(f"Refusing {name!r}: only the isolated e2e (demo) database is allowed.")
    if name == base.database:
        raise SystemExit(f"Refusing {name!r}: it is the DATABASE_URL (live) database.")
    return base.set(database=name).render_as_string(hide_password=False)


def check_manifest(path: Path, expected: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected.lower():
        raise SystemExit(
            f"Refusing: the manifest's SHA-256 is {actual}, not the approved {expected}."
        )


def check_identity(url: str, name: str) -> None:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            connected, marker = connection.execute(
                text(
                    "SELECT current_database(), shobj_description(oid, 'pg_database') "
                    "FROM pg_database WHERE datname = current_database()"
                )
            ).one()
    finally:
        engine.dispose()
    if connected != name or marker != DEMO_MARKER:
        raise SystemExit(
            "Refusing: the connected database is not the marked isolated demo database."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--expect-manifest-sha256", required=True)
    parser.add_argument("--database", default="lexflow_e2e")
    parser.add_argument("--confirm", type=int)
    args = parser.parse_args(argv)
    check_manifest(args.manifest, args.expect_manifest_sha256)
    url = isolated_url(args.database, Settings().database_url)
    check_identity(url, args.database)
    print(f"Checks passed: manifest SHA-256 as approved; database {args.database!r} is marked.")
    command = [sys.executable, "-m", "lexflow.cli.judgments", "import", str(args.manifest)]
    if args.confirm is not None:
        command += ["--confirm", str(args.confirm)]
    env = {**os.environ, "DATABASE_URL": url}
    # This interpreter and the CLI module; the arguments are the hash-checked manifest
    # path and an integer, never a shell string.
    return subprocess.run(command, cwd=SERVER_ROOT, env=env, check=False).returncode  # noqa: S603


if __name__ == "__main__":
    raise SystemExit(main())
