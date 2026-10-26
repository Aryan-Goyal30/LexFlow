"""Write the FICTIONAL demo case pack to server/tests/fixtures/demo-case/.

    python scripts/make_demo_case.py

The pack (a fictional trade mark dispute: PDFs, Word files, text files and a
manifest) is built by ``tests/demo_case.py`` and committed so the demo and the
end-to-end tests can upload real files; ``tests/test_demo_case.py`` checks the
committed copies against the builder and extracts each one with the real
extractors.
"""

from __future__ import annotations

import sys
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_ROOT))

from tests.demo_case import DEMO_DIR, DOCUMENTS, manifest_bytes  # noqa: E402


def main() -> int:
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    for name, _title, _date, _kind, build in DOCUMENTS:
        (DEMO_DIR / name).write_bytes(build())
        print(f"wrote {name}")
    (DEMO_DIR / "manifest.json").write_bytes(manifest_bytes())
    print("wrote manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
