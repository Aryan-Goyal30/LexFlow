"""Atomically update docs/verification/phase6/checkpoint.json.

    server\\.venv\\Scripts\\python docs/verification/phase6/update_checkpoint.py PATCH.json

PATCH.json is a JSON object whose top-level keys replace the checkpoint's keys
(a value of null deletes the key). The result is written to a temporary file
in the same folder, read back, validated (JSON, required fields and types),
and only then moved over the checkpoint with os.replace. On any failure the
previous checkpoint is left untouched. With --init and no checkpoint yet,
PATCH.json becomes the first checkpoint (it must pass the same validation).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

TARGET = Path(__file__).resolve().parent / "checkpoint.json"
REQUIRED: dict[str, type] = {
    "phase": int,
    "updated": str,
    "branch": str,
    "start_commit": str,
    "status": str,
    "current_batch": str,
    "batches": dict,
    "acceptance_criteria": dict,
    "latest_tests": dict,
    "decisions": dict,
    "deferred": dict,
    "migration": dict,
    "next_action": str,
    "latest_log_entry": str,
}


def validate(data: object) -> dict[str, object]:
    if not isinstance(data, dict):
        raise SystemExit("checkpoint invalid: not a JSON object")
    for key, kind in REQUIRED.items():
        if not isinstance(data.get(key), kind):
            raise SystemExit(
                f"checkpoint invalid: {key!r} missing or not {kind.__name__}"
            )
    return data


def main(argv: list[str]) -> int:
    init = "--init" in argv
    paths = [a for a in argv if a != "--init"]
    if len(paths) != 1:
        raise SystemExit(__doc__)
    patch = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
    if init:
        if TARGET.exists():
            raise SystemExit("--init: the checkpoint already exists; update it instead")
        current: dict[str, object] = {}
    else:
        current = json.loads(TARGET.read_text(encoding="utf-8"))
    for key, value in patch.items():
        if value is None:
            current.pop(key, None)
        else:
            current[key] = value
    text = json.dumps(current, indent=2, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(dir=TARGET.parent, prefix=".checkpoint-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        validate(json.loads(Path(tmp).read_text(encoding="utf-8")))
        os.replace(tmp, TARGET)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    print(f"checkpoint updated: {TARGET} ({len(current)} keys)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
