"""The offline evaluation of AI analysis (Phase 5 M9): every SYNTHETIC scenario
in ``tests/fixtures/analysis/synthetic-gold-v1.json`` behaves as stated, no
user-facing message carries operator detail, and the harness notices when a
scenario's behaviour changes. No provider is contacted."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SERVER_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = SERVER_ROOT / "scripts" / "evaluate_analysis.py"
FIXTURE = SERVER_ROOT / "tests" / "fixtures" / "analysis" / "synthetic-gold-v1.json"
CATEGORIES = {
    "quote-fidelity",
    "fabricated-citation",
    "evidence-reference",
    "contradiction",
    "outcome",
    "malformed-output",
    "insufficient-evidence",
    "provider-failure",
    "retry",
    "configuration",
}


@pytest.fixture(scope="module")
def harness() -> ModuleType:
    spec = importlib.util.spec_from_file_location("evaluate_analysis", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # its dataclasses look themselves up
    spec.loader.exec_module(module)
    return module


def gold() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def test_every_synthetic_scenario_behaves_as_stated(harness: ModuleType) -> None:
    report = harness.evaluate()
    assert report["not_as_expected"] == []
    assert report["messages_with_operator_words"] == []
    assert report["as_expected"] == report["scenarios"] == len(gold()["scenarios"])
    assert set(report["by_category"]) == CATEGORIES
    # The limitations are kept on purpose and stay visible in the report.
    assert {item["id"] for item in report["limitations"]} == {
        "ct-non-contradiction",
        "oc-paraphrase",
    }


def test_a_changed_behaviour_is_reported(harness: ModuleType, tmp_path: Path) -> None:
    data = gold()
    by_id = {s["id"]: s for s in data["scenarios"]}
    by_id["qf-exact"]["expected"]["kept"]["facts"] = 0
    by_id["pf-429-daily"]["expected"]["retry"] = True
    by_id["rt-timeout-then-ok"]["expected"]["trail"] = ["ready"]
    changed = tmp_path / "gold.json"
    changed.write_text(json.dumps(data), encoding="utf-8")
    report = harness.evaluate(changed)
    assert [m["id"] for m in report["not_as_expected"]] == [
        "qf-exact",
        "pf-429-daily",
        "rt-timeout-then-ok",
    ]


def test_the_fixture_is_synthetic_and_kept_apart_from_the_collection() -> None:
    data = gold()
    assert "SYNTHETIC" in data["notice"] and "not part of the judgment collection" in data["notice"]
    texts = [p["text"] for p in data["passages"]] + [j["text"] for j in data["judgments"]]
    assert all(text.startswith("SYNTHETIC.") for text in texts)
    assert all("SYNTHETIC" in j["title"] for j in data["judgments"])
    assert "SYNTHETIC" in data["case"]["title"]
    # Not a judgment manifest: without a "source" the importer refuses it.
    assert "source" not in data
    assert FIXTURE.parent.name == "analysis"
