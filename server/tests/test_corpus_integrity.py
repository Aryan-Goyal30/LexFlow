"""The corpus integrity check (Batch 5), on a tiny INVENTED corpus in a temporary folder.

The bytes are invented placeholders shaped like the real layout (an import
copy, its original as served, one with the legacy 4-byte length prefix); no
judgment text is involved and nothing connects to a database.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import struct
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "verify_corpus_integrity.py"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lexflow_corpus_integrity", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def corpus(tmp_path: Path) -> tuple[Path, str]:
    folder = tmp_path / "corpus"
    (folder / "original").mkdir(parents=True)
    judgments = []
    for n, prefixed in ((1, False), (2, True)):
        copy = f"%PDF-1.4 INVENTED test file {n}\n".encode()
        served = struct.pack("<I", len(copy)) + copy if prefixed else copy
        name = f"j{n}.pdf"
        (folder / name).write_bytes(copy)
        (folder / "original" / f"j{n}.as-served.pdf").write_bytes(served)
        url = f"https://api.sci.gov.in/jonew/judis/{n}.pdf"  # shape only; never fetched
        judgments.append(
            {
                "id": f"x-{n}",
                "title": f"INVENTED {n}",
                "file": name,
                "source_url": url,
                "provenance": {
                    "retrieved_from": url,
                    "original_sha256": hashlib.sha256(served).hexdigest(),
                    **({"original_transform": "4-byte prefix removed"} if prefixed else {}),
                },
            }
        )
    manifest = {"source": {"key": "invented-test"}, "judgments": judgments}
    path = folder / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return folder, hashlib.sha256(path.read_bytes()).hexdigest()


def test_an_intact_corpus_verifies_and_the_lock_is_never_overwritten(tmp_path: Path) -> None:
    script = load()
    folder, digest = corpus(tmp_path)
    lock = tmp_path / "lock.json"
    data = script.write_lock(folder, lock, digest)
    assert [e["transformed"] for e in data["judgments"]] == [False, True]
    assert script.verify(folder, data) == []
    with pytest.raises(SystemExit, match="never overwritten"):
        script.write_lock(folder, lock, digest)


def test_the_lock_is_written_only_for_the_approved_manifest(tmp_path: Path) -> None:
    script = load()
    folder, _ = corpus(tmp_path)
    with pytest.raises(SystemExit, match="not 0000"):
        script.write_lock(folder, tmp_path / "lock.json", "0" * 64)


@pytest.mark.parametrize(
    ("tamper", "problem"),
    [
        (lambda f: (f / "j1.pdf").write_bytes(b"%PDF-1.4 changed\n"), "import copy's SHA-256"),
        (lambda f: (f / "original" / "j2.as-served.pdf").write_bytes(b"x"), "original's SHA-256"),
        (lambda f: (f / "j1.pdf").unlink(), "missing"),
        (lambda f: (f / "extra.pdf").write_bytes(b"%PDF-1.4\n"), "not in the lock"),
        (lambda f: (f / "manifest.json").write_text("{}", encoding="utf-8"), "approved manifest"),
    ],
)
def test_every_change_is_reported_and_nothing_is_repaired(
    tmp_path: Path, tamper: object, problem: str
) -> None:
    script = load()
    folder, digest = corpus(tmp_path)
    data = script.write_lock(folder, tmp_path / "lock.json", digest)
    tamper(folder)  # type: ignore[operator]
    before = {p: p.read_bytes() for p in folder.rglob("*") if p.is_file()}
    problems = script.verify(folder, data)
    assert any(problem in p for p in problems), problems
    assert {p: p.read_bytes() for p in folder.rglob("*") if p.is_file()} == before


def test_an_address_off_the_official_hosts_is_reported(tmp_path: Path) -> None:
    script = load()
    folder, digest = corpus(tmp_path)
    data = script.write_lock(folder, tmp_path / "lock.json", digest)
    data["judgments"][0]["source_url"] = "https://mirror.example.org/1.pdf"
    assert any("official host" in p for p in script.verify(folder, data))
