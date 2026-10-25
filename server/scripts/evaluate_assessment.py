"""Offline evaluation of the outcome-assessment checks on SYNTHETIC scenarios (Phase 7 demo).

    .venv\\Scripts\\python scripts/evaluate_assessment.py            print the report
    .venv\\Scripts\\python scripts/evaluate_assessment.py --write    also write
        docs/verification/phase7/assessment-eval.json and assessment-eval.md
    ... --write --report-name assessment-eval-2026-10-25
        writes those names instead, keeping earlier reports

Each scenario in ``tests/fixtures/assessment/synthetic-scenarios-v1.json``
(invented findings and invented judgment passages; not case law, not
lawyer-labelled) runs through the same code as the API (``service.assess``:
the evidence gate, the provider call with one retry for an unreadable answer,
parsing and ``assessment-grounding-1`` validation), and its outcome is compared
with what the scenario expects:

- ``scripted``: the scripted assessment provider (deterministic, not AI);
- ``answer``: a prepared answer, as an adversarial model might return;
- ``attempts``: provider errors, unreadable or cut-off answers, then recovery;
- ``config``: which provider the settings allow (``.env`` is not read).

There is no pass mark: a mismatch means the code no longer does what the
scenario says, and the exit status is 1. This measures LexFlow's checks and
error handling on invented data, **not legal accuracy**, and no model is
called. Nothing leaves this computer and no database is touched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

SERVER_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = SERVER_ROOT.parent
FIXTURE = SERVER_ROOT / "tests" / "fixtures" / "assessment" / "synthetic-scenarios-v1.json"
OUT_DIR = REPO_ROOT / "docs" / "verification" / "phase7"
# A throwaway name: settings need a URL; nothing ever connects to it.
TEST_URL = "postgresql+psycopg://eval@127.0.0.1:1/lexflow_eval_test"

os.environ.setdefault("DATABASE_URL", TEST_URL)
sys.path.insert(0, str(SERVER_ROOT))

from pydantic import ValidationError  # noqa: E402

from lexflow.analysis.provider import ProviderError, Response, Unavailable  # noqa: E402
from lexflow.assessment import output, prompt, service, validation  # noqa: E402
from lexflow.assessment.inputs import InputFinding, InputPrecedent, Inputs  # noqa: E402
from lexflow.assessment.provider import AssessmentRequest, provider_for  # noqa: E402
from lexflow.assessment.scripted import ScriptedAssessmentProvider  # noqa: E402
from lexflow.config import Settings  # noqa: E402

B10 = {
    1: "Feature disabled",
    2: "Enabled with accepted findings and a retrieved synthetic precedent",
    3: "No accepted findings",
    4: "No retrieved (accepted) precedents",
    5: "Unsupported citation",
    6: "Quote not present in the source",
    7: "Unsupported reasoning",
    8: "A precedent that cuts against the position",
    9: "Mixed evidence",
    10: "Rejected or unreviewed findings excluded",
    11: "Synthetic label preserved",
    12: "A user without permission",
    13: "Archived case",
    14: "Review, edit and rejection",
    15: "Assessment export behaviour",
    16: "Provider failure and recovery",
}


def build_inputs(base: dict[str, Any], chosen: dict[str, list[str]]) -> Inputs:
    findings = {f["id"]: f for f in base["findings"]}
    precedents = {p["id"]: p for p in base["precedents"]}
    inputs = Inputs()
    for fid in chosen.get("findings", []):
        f = findings[fid]
        inputs.findings.append(InputFinding(f["kind"], fid, f["text"], False, 1))
    for pid in chosen.get("precedents", []):
        p = precedents[pid]
        inputs.precedents.append(
            InputPrecedent(
                id=pid,
                summary=f"SYNTHETIC accepted comparison {pid}",
                edited=False,
                review_version=1,
                judgment_id=uuid.uuid5(uuid.NAMESPACE_URL, f"lexflow-eval/{pid}"),
                title=p["title"],
                court=p["court"],
                citation=p["citation"],
                year=p["year"],
                synthetic=True,
                chunk_id=uuid.uuid5(uuid.NAMESPACE_URL, f"lexflow-eval/{pid}/chunk"),
                section_number=1,
                page_number=1,
                text=p["text"],
                content_sha256=hashlib.sha256(p["text"].encode()).hexdigest(),
            )
        )
    left_out = {f for f in findings if f not in chosen.get("findings", [])}
    left_out |= {p for p in precedents if p not in chosen.get("precedents", [])}
    if left_out:
        inputs.excluded = {"unreviewed": len(left_out)}
    return inputs


class Prepared:
    """A provider that replays prepared attempts (answers, errors, cut-offs)."""

    name, model = "scripted", "prepared-eval-v1"

    def __init__(self, attempts: list[dict[str, Any]]) -> None:
        self.attempts = list(attempts)
        self.calls = 0

    def generate(self, request: AssessmentRequest) -> Response:
        self.calls += 1
        step = self.attempts.pop(0) if self.attempts else {"text": ""}
        if "error" in step:
            raise ProviderError(step["error"], "SYNTHETIC provider failure.", retry=True)
        if step.get("truncated"):
            return Response(text="", truncated=True)
        if step.get("scripted"):
            return ScriptedAssessmentProvider().generate(request)
        if "answer" in step:
            return Response(text=json.dumps(step["answer"]))
        return Response(text=str(step.get("text", "")))


def observe(outcome: service.Assessed, calls: int) -> dict[str, Any]:
    result = outcome.result or {}
    removed = {r["code"]: r["count"] for r in (outcome.removed or {}).get("reasons", [])}
    return {
        "status": outcome.status,
        "reasonCode": outcome.reason_code,
        "uncertainty": result.get("uncertainty"),
        "refs": [p["ref"] for p in result.get("precedents", [])],
        "stances": [p["stance"] for p in result.get("precedents", [])],
        "steps": len(result.get("reasoning", [])),
        "removed": removed,
        "allSynthetic": result.get("allPrecedentsSynthetic"),
        "demoOnly": result.get("demoOnly"),
        "called": outcome.called,
        "calls": calls,
        "text": json.dumps(result),
    }


def run_config(s: dict[str, Any]) -> dict[str, Any]:
    values = {
        "DATABASE_URL": TEST_URL,
        "LEXFLOW_ENV": "test",
        "GEMINI_API_KEY": "",
        **s["settings"],
    }
    values.setdefault("GEMINI_MODEL", "")
    try:
        settings = Settings(_env_file=None, **values)
    except ValidationError:
        return {"refused": True}
    provider = provider_for(settings)
    if isinstance(provider, Unavailable):
        return {"unavailable": provider.code}
    return {"provider": provider.name}


def run_scenario(base: dict[str, Any], s: dict[str, Any]) -> dict[str, Any]:
    if s["kind"] == "config":
        return run_config(s)
    inputs = build_inputs(base, s["inputs"])
    if s["kind"] == "scripted":
        provider: Any = ScriptedAssessmentProvider()
        prepared = None
    elif s["kind"] == "answer":
        provider = prepared = Prepared([{"answer": s["answer"]}])
    else:
        provider = prepared = Prepared(s["attempts"])
    outcome = service.assess(provider, inputs)
    calls = prepared.calls if prepared is not None else int(outcome.called)
    return observe(outcome, calls)


def matches(expected: dict[str, Any], observed: dict[str, Any]) -> bool:
    for key, value in expected.items():
        if key == "absent":
            if any(token in observed.get("text", "") for token in value):
                return False
        elif observed.get(key) != value:
            return False
    return True


def evaluate(fixture: Path = FIXTURE) -> dict[str, Any]:
    raw = fixture.read_bytes()
    data = json.loads(raw)
    base = data["base"]
    outcomes = []
    covered: Counter[int] = Counter()
    reasons: Counter[str] = Counter()
    mismatches = []
    for s in data["scenarios"]:
        observed = run_scenario(base, s)
        ok = matches(s["expect"], observed)
        for item in s["covers"]:
            covered[item] += 1
        for code, n in observed.get("removed", {}).items():
            reasons[code] += n
        shown = {k: v for k, v in observed.items() if k != "text"}
        outcomes.append({"id": s["id"], "kind": s["kind"], "covers": s["covers"], "ok": ok,
                         "observed": shown})  # fmt: skip
        if not ok:
            mismatches.append({"id": s["id"], "expected": s["expect"], "observed": shown})
    elsewhere = data.get("covered_elsewhere", [])
    for entry in elsewhere:
        for item in entry["covers"]:
            covered.setdefault(item, 0)
    return {
        "fixture": str(fixture.relative_to(SERVER_ROOT)).replace("\\", "/"),
        "fixture_sha256": hashlib.sha256(raw).hexdigest(),
        "pipeline": {
            "promptVersion": prompt.PROMPT_VERSION,
            "schemaVersion": output.SCHEMA_VERSION,
            "validatorVersion": validation.VALIDATOR_VERSION,
        },
        "scenarios": len(outcomes),
        "as_expected": sum(1 for o in outcomes if o["ok"]),
        "not_as_expected": mismatches,
        "b10": {
            str(n): {
                "scenario": name,
                "here": covered.get(n, 0),
                "elsewhere": [e["test"] for e in elsewhere if n in e["covers"]],
            }
            for n, name in B10.items()
        },
        "removal_reasons_observed": dict(sorted(reasons.items())),
        "outcomes": outcomes,
    }


def markdown(report: dict[str, Any]) -> str:
    pipeline = report["pipeline"]
    lines = [
        "# Outcome assessment — offline evaluation (SYNTHETIC scenarios)",
        "",
        "Generated by `server/scripts/evaluate_assessment.py --write`. No model is called and",
        "no database is used. This checks LexFlow's gate, provider handling and validation on",
        "invented data; it says **nothing about legal accuracy**, and the scenarios are not",
        "lawyer-labelled. There is no pass mark: each scenario states its expected outcome.",
        "",
        f"- Fixture: `server/{report['fixture']}` (SHA-256 `{report['fixture_sha256']}`)",
        f"- Pipeline: prompt `{pipeline['promptVersion']}`, schema `{pipeline['schemaVersion']}`,"
        f" validator `{pipeline['validatorVersion']}`",
        f"- Scenarios: {report['scenarios']}; as expected: {report['as_expected']}; "
        f"not as expected: {len(report['not_as_expected'])}",
        "",
        "## Demo scenarios (PHASE 7 plan B10) and where each is covered",
        "",
        "| # | Scenario | Here | Elsewhere |",
        "|---:|---|---:|---|",
    ]
    for number, row in report["b10"].items():
        elsewhere = "; ".join(row["elsewhere"]) or "—"
        lines.append(f"| {number} | {row['scenario']} | {row['here']} | {elsewhere} |")
    lines += ["", "## Scenarios", "", "| Scenario | Kind | Covers | Outcome | As expected |"]
    lines += ["|---|---|---|---|---|"]
    for o in report["outcomes"]:
        observed = o["observed"]
        outcome = observed.get("status") or (
            "refused by the settings"
            if observed.get("refused")
            else next(iter(observed.values()), "")
        )
        detail = observed.get("reasonCode") or observed.get("uncertainty") or ""
        lines.append(
            f"| `{o['id']}` | {o['kind']} | {', '.join(map(str, o['covers']))} | "
            f"{outcome}{f' ({detail})' if detail else ''} | {'yes' if o['ok'] else '**no**'} |"
        )
    lines += ["", "## Removal reasons observed", ""]
    lines += [f"- `{code}`: {n}" for code, n in report["removal_reasons_observed"].items()]
    if report["not_as_expected"]:
        lines += ["", "## Not as expected", ""]
        lines += [
            f"- `{m['id']}`: expected `{json.dumps(m['expected'])}`, observed "
            f"`{json.dumps(m['observed'])}`"
            for m in report["not_as_expected"]
        ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--write", action="store_true", help="write the JSON and Markdown report")
    parser.add_argument("--report-name", default="assessment-eval")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,80}", args.report_name):
        parser.error("--report-name: letters, digits, '.', '_' and '-' only")
    report = evaluate()
    text = markdown(report)
    print(text)
    if args.write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        target = OUT_DIR / args.report_name
        target.with_suffix(".json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
        target.with_suffix(".md").write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {target.with_suffix('.json')} and {target.with_suffix('.md').name}")
    return 0 if not report["not_as_expected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
