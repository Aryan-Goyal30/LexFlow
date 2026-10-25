"""The offline assessment evaluation (Phase 7 demo) runs and every SYNTHETIC
scenario behaves as it states. No model, no database."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "evaluate_assessment.py"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("evaluate_assessment", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_every_synthetic_scenario_behaves_as_stated() -> None:
    report = load().evaluate()
    assert report["not_as_expected"] == []
    assert report["scenarios"] == report["as_expected"] >= 20
    # Every demo scenario of the plan is covered here or by a named test.
    for number, row in report["b10"].items():
        assert row["here"] or row["elsewhere"], number


def test_the_report_says_what_it_is_not() -> None:
    module = load()
    text = " ".join(module.markdown(module.evaluate()).split())
    assert "nothing about legal accuracy" in text
    assert "not lawyer-labelled" in text
