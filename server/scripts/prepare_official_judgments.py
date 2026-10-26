"""Build a judgment import manifest from a hand-picked folder of official PDFs.

    python scripts/prepare_official_judgments.py FOLDER --checked-by "NAME"
        [--profile sci-escr] [--checked-on YYYY-MM-DD] [--attribution TEXT]

FOLDER holds the PDFs downloaded by hand from the official portal and a
``selection.csv`` filled from the portal's record (see
``lexflow/services/judgment_selection.py`` for the columns). The script
writes ``FOLDER/manifest.json`` and prints the next command (a dry-run
preview); it makes no network request and does not touch any database.
Importing genuine judgments needs the owner's approval first.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_ROOT))

from lexflow.services.judgment_selection import (  # noqa: E402
    PROFILES,
    SelectionError,
    build_manifest,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="sci-escr")
    parser.add_argument("--checked-by", required=True, help="who read the source's terms")
    parser.add_argument("--checked-on", type=date.fromisoformat, default=date.today())
    parser.add_argument("--attribution", help="replace the profile's proposed attribution")
    args = parser.parse_args(argv)
    try:
        manifest = build_manifest(
            args.folder,
            PROFILES[args.profile],
            checked_by=args.checked_by,
            checked_on=args.checked_on,
            attribution=args.attribution,
        )
    except SelectionError as error:
        for problem in error.problems:
            print(f"error: {problem}", file=sys.stderr)
        return 1
    out = args.folder / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out} with {len(manifest['judgments'])} judgments")
    print(
        "next, only after the owner approves the import, and with DATABASE_URL naming the\n"
        "approved evaluation or demo database (never the live one), preview it:\n"
        f"  python -m lexflow.cli.judgments import {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
