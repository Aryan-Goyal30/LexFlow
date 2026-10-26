"""The real-model evaluation harness without any real model (Batch 4, M8).

Plans are built from the FICTIONAL and SYNTHETIC fixtures only; the
synthetic judgment lookup (a read of ``lexflow_e2e``) is replaced by the
fixture passages here, so no database is needed. Execution is exercised with the
scripted provider; the Gemini path is refused unless the approval is the
plan's own SHA-256 and the configured provider is Gemini.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from lexflow.analysis.provider import ProviderError
from lexflow.analysis.scripted import ScriptedProvider
from tests.analysis_fakes import judgment_passage

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "evaluate_analysis_real.py"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lexflow_real_eval", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.synthetic_passages = lambda: [judgment_passage()]  # type: ignore[attr-defined]
    return module


def test_the_plan_is_deterministic_and_makes_no_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    harness = load()

    def never(*args: object, **kwargs: object) -> None:
        raise AssertionError("planning must not build a provider")

    monkeypatch.setattr(harness, "provider_for", never)
    assert harness.main(["--out", str(tmp_path / "a")]) == 0
    assert harness.main(["--out", str(tmp_path / "b")]) == 0
    a, b = ((tmp_path / d / "plan.json").read_bytes() for d in "ab")
    assert a == b
    plan = json.loads(a)
    assert [s["scenario"] for s in plan["scenarios"]][:2] == [
        "S1-demo-pack",
        "S2-demo-with-injection",
    ]
    assert plan["data_scope"]["genuine_judgment_passages"] == 0
    assert plan["data_scope"]["judgments_used"] == ["Asha Rao v. Bharat Traders (SYNTHETIC)"]
    assert "No model call made" in capsys.readouterr().out


def test_execution_needs_the_approval_of_this_exact_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = load()

    def never(*args: object, **kwargs: object) -> None:
        raise AssertionError("nothing may be called without the approval")

    monkeypatch.setattr(harness, "provider_for", never)
    monkeypatch.setattr(harness, "execute", never)
    args = ["--out", str(tmp_path), "--execute", "--approval", "0" * 64]
    with pytest.raises(SystemExit, match="SHA-256 of this exact plan"):
        harness.main(args)


def test_execution_refuses_a_provider_other_than_gemini(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = load()
    harness.main(["--out", str(tmp_path)])
    digest = hashlib.sha256((tmp_path / "plan.json").read_bytes()).hexdigest()
    monkeypatch.setattr(harness, "provider_for", lambda settings: ScriptedProvider())
    monkeypatch.setattr(harness, "execute", lambda *a, **k: pytest.fail("must not execute"))
    with pytest.raises(SystemExit, match="not Gemini"):
        harness.main(["--out", str(tmp_path), "--execute", "--approval", digest])


def test_each_run_keeps_its_raw_answer_and_validated_result(tmp_path: Path) -> None:
    harness = load()
    evidence = harness.scenarios([])
    small = {k: evidence[k] for k in ("S2-demo-with-injection", "S4-insufficient")}
    summary = harness.execute(small, ScriptedProvider(), tmp_path, repeats=1, spacing=0)
    assert [(s["scenario"], s["status"]) for s in summary] == [
        ("S2-demo-with-injection", "ready"),
        ("S4-insufficient", "ready"),
    ]
    row = json.loads((tmp_path / "S2-demo-with-injection-1.json").read_text(encoding="utf-8"))
    assert row["raw"] and row["raw"][0]["text"]
    flagged = row["result"]["instruction_like_passages"]
    assert [p["document_name"] for p in flagged] == ["SYNTHETIC-note-to-file.txt"]


def test_a_non_synthetic_judgment_passage_stops_the_plan() -> None:
    harness = load()
    real = replace(judgment_passage(), synthetic=False)
    with pytest.raises(SystemExit, match="not from a synthetic source"):
        harness.plan_of(harness.scenarios([real]))


def test_the_allowed_hashes_are_exactly_the_synthetic_fixture_files() -> None:
    harness = load()
    manifest = json.loads(harness.SYNTHETIC_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["source"]["synthetic"] is True
    allowed = harness.synthetic_hashes()
    assert len(allowed) == len(manifest["judgments"]) == 13


def test_the_genuine_scope_refuses_a_synthetic_passage_and_says_what_it_sends() -> None:
    harness = load()
    with pytest.raises(SystemExit, match="not from the genuine corpus"):
        harness.plan_of(harness.scenarios([judgment_passage()]), "genuine")
    real = replace(judgment_passage(), synthetic=False, title="TEST ONLY genuine stand-in")
    plan = harness.plan_of(harness.scenarios([real]), "genuine")
    assert plan["data_scope"]["judgments"].startswith("GENUINE")
    assert plan["data_scope"]["genuine_judgment_passages"] == 3  # S1, S2, S5
    assert "lawyer's review" in plan["limitations"][0]


def test_genuine_passages_are_checked_against_the_committed_corpus_lock() -> None:
    harness = load()
    key, hashes = harness.genuine_hashes()
    assert key == "sci-judgments" and len(hashes) == 17


class Flaky:
    """Fails with the given errors first, then answers like the scripted provider."""

    name, model = "gemini", "fake-model"

    def __init__(self, errors: list[ProviderError]) -> None:
        self.errors, self.calls = list(errors), 0
        self.scripted = ScriptedProvider()

    def generate(self, request: Any) -> Any:
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return self.scripted.generate(request)


def unavailable() -> ProviderError:
    return ProviderError(
        "provider-unavailable", "5xx", retry=True, diagnostic={"httpStatus": "503"}
    )


def stored(folder: Path, scenario: str, repeat: int, status: str, code: str | None = None) -> Path:
    row: dict[str, Any] = {"scenario": scenario, "repeat": repeat, "status": status, "raw": []}
    if status == "ready":
        row |= {"raw": [{"text": "x"}], "result": {"kept": True}}
    else:
        row["code"] = code
    path = folder / f"{scenario}-{repeat}.json"
    path.write_text(json.dumps(row), encoding="utf-8")
    return path


def test_only_transient_failures_are_retried_with_backoff_and_recorded(tmp_path: Path) -> None:
    harness = load()
    evidence = harness.scenarios([])
    ready = stored(tmp_path, "S1-demo-pack", 1, "ready")
    before = ready.read_bytes()
    stored(tmp_path, "S4-insufficient", 1, "failed", "provider-unavailable")
    stored(tmp_path, "S6-missing-exhibit", 1, "failed", "provider-rejected")
    delays: list[float] = []
    provider = Flaky([unavailable()])
    report = harness.retry_failed(evidence, provider, tmp_path, spacing=0, sleep=delays.append)
    assert ready.read_bytes() == before  # a ready run is never touched
    s4 = json.loads((tmp_path / "S4-insufficient-1.json").read_text(encoding="utf-8"))
    assert s4["status"] == "ready" and s4["final_outcome"] == "ready"
    assert [a["code"] for a in s4["attempts"]] == [
        "provider-unavailable",
        "provider-unavailable",
        "ready",
    ]
    assert s4["attempts"][1]["http_status"] == "503" and s4["attempts"][1]["kind"] == "api"
    assert delays == [30, 60]  # exponential back-off
    s6 = json.loads((tmp_path / "S6-missing-exhibit-1.json").read_text(encoding="utf-8"))
    assert s6["status"] == "failed" and "not a transient failure" in s6["final_outcome"]
    assert provider.calls == 2  # the permanent error is never retried
    assert (tmp_path / "original-failed" / "S4-insufficient-1.json").is_file()
    assert report["calls_before"] == 3 and report["calls_after"] == 5


def test_the_call_ceiling_is_never_exceeded(tmp_path: Path) -> None:
    harness = load()
    stored(tmp_path, "S4-insufficient", 1, "failed", "provider-unavailable")
    provider = Flaky([unavailable(), unavailable()])
    harness.retry_failed(
        harness.scenarios([]), provider, tmp_path, ceiling=2, spacing=0, sleep=lambda s: None
    )
    row = json.loads((tmp_path / "S4-insufficient-1.json").read_text(encoding="utf-8"))
    assert provider.calls == 0 and "ceiling" in row["final_outcome"]


def test_the_genuine_evaluation_is_separate_and_needs_its_own_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = load()
    real = replace(judgment_passage(), synthetic=False, title="TEST ONLY genuine stand-in")
    monkeypatch.setattr(harness, "genuine_passages", lambda: [real])
    assert harness.OUTS["genuine"] != harness.OUTS["synthetic"]  # never the same results
    harness.main(["--out", str(tmp_path / "s")])
    synthetic = hashlib.sha256((tmp_path / "s" / "plan.json").read_bytes()).hexdigest()

    def never(*args: object, **kwargs: object) -> None:
        raise AssertionError("no provider may be built without the genuine plan's approval")

    monkeypatch.setattr(harness, "provider_for", never)
    with pytest.raises(SystemExit, match="SHA-256 of this exact plan"):
        harness.main(
            [
                "--judgments",
                "genuine",
                "--out",
                str(tmp_path / "g"),
                "--execute",
                "--approval",
                synthetic,
            ]
        )


def test_results_of_one_plan_are_never_mixed_with_another(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = load()
    harness.main(["--out", str(tmp_path)])
    digest = hashlib.sha256((tmp_path / "plan.json").read_bytes()).hexdigest()
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "plan-sha256.txt").write_text("0" * 64, encoding="utf-8")
    monkeypatch.setattr(harness, "provider_for", lambda s: pytest.fail("must not get this far"))
    with pytest.raises(SystemExit, match="results of another plan"):
        harness.main(["--out", str(tmp_path), "--execute", "--approval", digest])
