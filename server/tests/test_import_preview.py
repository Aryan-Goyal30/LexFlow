"""The import preview's database guard (Batch 2). Offline: nothing connects."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "preview_judgment_import.py"
LIVE = "postgresql+psycopg://user:secret@127.0.0.1:5432/lexflow"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lexflow_import_preview", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("name", "configured", "problem"),
    [
        ("lexflow", LIVE, "only a test or e2e database"),
        ("lexflow_latest", LIVE, "only a test or e2e database"),
        ("lexflow_e2e", LIVE.replace("/lexflow", "/lexflow_e2e"), "DATABASE_URL"),
        ("lexflow_e2e", LIVE + "?dbname=lexflow", "dbname or service"),
    ],
)
def test_the_preview_refuses_the_live_or_an_unnamed_database(
    name: str, configured: str, problem: str
) -> None:
    with pytest.raises(SystemExit, match=problem):
        load().target_url(name, configured)


def test_the_preview_targets_only_the_named_database() -> None:
    url = load().target_url("lexflow_e2e", LIVE)
    assert url.endswith("/lexflow_e2e")


IMPORT_SCRIPT = SCRIPT.parent / "import_judgments_isolated.py"


def load_import() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lexflow_import_isolated", IMPORT_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("name", "configured", "problem"),
    [
        ("lexflow", LIVE, "only the isolated e2e"),
        ("lexflow_test", LIVE, "only the isolated e2e"),
        ("lexflow_e2e", LIVE.replace("/lexflow", "/lexflow_e2e"), "DATABASE_URL"),
        ("lexflow_e2e", LIVE + "?service=x", "dbname or service"),
    ],
)
def test_the_import_refuses_anything_but_the_isolated_demo_database(
    name: str, configured: str, problem: str
) -> None:
    with pytest.raises(SystemExit, match=problem):
        load_import().isolated_url(name, configured)


def test_the_import_refuses_a_manifest_other_than_the_approved_one(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit, match="not the approved"):
        load_import().check_manifest(manifest, "0" * 64)


def test_the_import_stops_before_connecting_when_the_manifest_differs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_import()

    def never(*args: object, **kwargs: object) -> None:
        raise AssertionError("nothing may connect or run before the checks pass")

    monkeypatch.setattr(module, "check_identity", never)
    monkeypatch.setattr(module.subprocess, "run", never)
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit, match="not the approved"):
        module.main([str(manifest), "--expect-manifest-sha256", "0" * 64, "--confirm", "17"])
