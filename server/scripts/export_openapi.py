"""Write the API's OpenAPI document to server/openapi.json.

    .venv\\Scripts\\python scripts/export_openapi.py           write the file
    .venv\\Scripts\\python scripts/export_openapi.py --check   fail if it is out of date

The front end generates its TypeScript types from this file
(``npm run api:types``), so CI checks both steps for drift.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parent.parent
TARGET = SERVER_ROOT / "openapi.json"

# Building the schema never connects to the database, but settings require a URL.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused@127.0.0.1:1/unused")
sys.path.insert(0, str(SERVER_ROOT))

from lexflow.main import create_app  # noqa: E402 - needs the path and environment above


def render() -> str:
    spec = create_app().openapi()
    return json.dumps(spec, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    text = render()
    if "--check" in sys.argv:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if current.replace("\r\n", "\n") != text:
            print("server/openapi.json is out of date. Run: python scripts/export_openapi.py")
            return 1
        print("server/openapi.json is up to date")
        return 0
    TARGET.write_bytes(text.encode("utf-8"))
    print(f"wrote {TARGET.relative_to(SERVER_ROOT.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
