"""Verify the genuine judgment corpus against its recorded hashes and provenance.

    .venv\\Scripts\\python scripts/verify_corpus_integrity.py verify FOLDER --lock LOCK
        [--database lexflow_e2e]
    .venv\\Scripts\\python scripts/verify_corpus_integrity.py write-lock FOLDER --lock LOCK
        --expect-manifest-sha256 HEX

The corpus files live outside Git (``server/var/judgments/``); the lock file
(``docs/verification/batch2/corpus-sci-tm-v2.lock.json``) is small, holds no
judgment text, and can be committed, so a change to the folder cannot also
change what it is checked against.

``verify`` (read-only; it never downloads, replaces or modifies anything):

1. ``manifest.json`` has the SHA-256 the lock records (the approved manifest);
2. each judgment's import copy and its original as served (``original/``)
   have the recorded SHA-256; where a transformation is recorded, the import
   copy is exactly the original without its 4-byte little-endian length
   prefix (whose value is the length of the rest), and otherwise the two are
   identical;
3. the manifest's provenance (source URL, retrieval address, original hash)
   matches the lock, and every address is on an official host;
4. no PDF is missing, and none is in the folder that the lock does not list;
5. with ``--database``, the imported records match the manifest
   (``verify_judgment_import.py``, read-only, same database guards).

Exit status 1 on any problem, with every problem listed.

``write-lock`` creates the lock once from a folder whose manifest has the
approved SHA-256, after checking every file against the manifest's own
provenance. It refuses to overwrite an existing lock.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import struct
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SERVER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_ROOT))

LOCK_FORMAT = "lexflow-corpus-lock/1"
OFFICIAL_HOSTS = frozenset({"api.sci.gov.in", "main.sci.gov.in", "www.sci.gov.in", "sci.gov.in"})


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def original_of(file: str) -> str:
    return f"original/{file[:-4]}.as-served.pdf"


def _official(url: str | None) -> bool:
    return bool(url) and (urlsplit(url or "").hostname or "").lower() in OFFICIAL_HOSTS


def write_lock(folder: Path, lock: Path, expected: str) -> dict[str, Any]:
    if lock.exists():
        raise SystemExit(f"Refusing: {lock} exists; a lock is never overwritten.")
    manifest_path = folder / "manifest.json"
    digest = sha256(manifest_path)
    if digest != expected.lower():
        raise SystemExit(f"Refusing: the manifest's SHA-256 is {digest}, not {expected}.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = []
    for j in manifest["judgments"]:
        record = j.get("provenance", {})
        original = folder / original_of(j["file"])
        if sha256(original) != record.get("original_sha256"):
            raise SystemExit(f"Refusing: {original.name} does not match its recorded hash.")
        entries.append(
            {
                "id": j["id"],
                "title": j["title"],
                "file": j["file"],
                "sha256": sha256(folder / j["file"]),
                "original_file": original_of(j["file"]),
                "original_sha256": record["original_sha256"],
                "transformed": bool(record.get("original_transform")),
                "source_url": j["source_url"],
                "retrieved_from": record.get("retrieved_from"),
                "retrieved_at": record.get("retrieved_at"),
            }
        )
    data = {
        "format": LOCK_FORMAT,
        "source_key": manifest["source"]["key"],
        "manifest_sha256": digest,
        "judgments": entries,
    }
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return data


def verify(folder: Path, lock_data: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if lock_data.get("format") != LOCK_FORMAT:
        return [f"the lock is not {LOCK_FORMAT}"]
    manifest_path = folder / "manifest.json"
    if not manifest_path.is_file():
        return ["manifest.json is missing"]
    if sha256(manifest_path) != lock_data["manifest_sha256"]:
        problems.append("manifest.json differs from the approved manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_id = {j["id"]: j for j in manifest.get("judgments", [])}
    expected_files = set()
    for entry in lock_data["judgments"]:
        name = entry["file"]
        expected_files.update({name, entry["original_file"]})
        copy, original = folder / name, folder / entry["original_file"]
        if not copy.is_file() or not original.is_file():
            problems.append(f"{name}: the import copy or the original is missing")
            continue
        copy_bytes, original_bytes = copy.read_bytes(), original.read_bytes()
        if hashlib.sha256(copy_bytes).hexdigest() != entry["sha256"]:
            problems.append(f"{name}: the import copy's SHA-256 differs from the lock")
        if hashlib.sha256(original_bytes).hexdigest() != entry["original_sha256"]:
            problems.append(f"{name}: the original's SHA-256 differs from the lock")
        if entry["transformed"]:
            prefix_ok = (
                len(original_bytes) > 4
                and struct.unpack("<I", original_bytes[:4])[0] == len(original_bytes) - 4
                and original_bytes[4:] == copy_bytes
            )
            if not prefix_ok:
                problems.append(f"{name}: the copy is not the original minus its length prefix")
        elif original_bytes != copy_bytes:
            problems.append(
                f"{name}: the copy differs from the original though no change is recorded"
            )
        j = by_id.get(entry["id"])
        record = (j or {}).get("provenance", {})
        if j is None:
            problems.append(f"{entry['id']}: not in the manifest")
        elif (
            j["source_url"] != entry["source_url"]
            or record.get("retrieved_from") != entry["retrieved_from"]
            or record.get("original_sha256") != entry["original_sha256"]
        ):
            problems.append(f"{entry['id']}: the manifest's provenance differs from the lock")
        if not _official(entry["source_url"]) or not _official(entry["retrieved_from"]):
            problems.append(f"{entry['id']}: an address is not on an official host")
    present = {str(p.relative_to(folder)).replace("\\", "/") for p in folder.rglob("*.pdf")}
    problems += [
        f"{name}: in the folder but not in the lock" for name in sorted(present - expected_files)
    ]
    return problems


def check_database(folder: Path, database: str) -> list[str]:
    spec = importlib.util.spec_from_file_location(
        "lexflow_verify_import", SERVER_ROOT / "scripts" / "verify_judgment_import.py"
    )
    if spec is None or spec.loader is None:
        raise SystemExit("Cannot load verify_judgment_import.py.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    code = module.main([str(folder / "manifest.json"), "--database", database])
    return [] if code == 0 else [f"the records in {database} do not match the manifest"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["verify", "write-lock"], nargs="?", default="verify")
    parser.add_argument("folder", type=Path)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--expect-manifest-sha256")
    parser.add_argument("--database")
    args = parser.parse_args(argv)
    if args.command == "write-lock":
        if not args.expect_manifest_sha256:
            raise SystemExit("write-lock needs --expect-manifest-sha256 (the approved manifest).")
        data = write_lock(args.folder, args.lock, args.expect_manifest_sha256)
        print(f"wrote {args.lock}: {len(data['judgments'])} judgments")
        return 0
    lock_data = json.loads(args.lock.read_text(encoding="utf-8"))
    problems = verify(args.folder, lock_data)
    if args.database:
        problems += check_database(args.folder, args.database)
    for problem in problems:
        print("PROBLEM:", problem)
    count = len(lock_data.get("judgments", []))
    print(f"corpus {lock_data.get('source_key')}: {count} judgments; {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
