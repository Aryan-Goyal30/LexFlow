"""Offline evaluation of AI case analysis on SYNTHETIC scenarios (Phase 5 M9).

    .venv\\Scripts\\python scripts/evaluate_analysis.py            print the report
    .venv\\Scripts\\python scripts/evaluate_analysis.py --write    also write
        docs/verification/phase5/analysis-eval.json and analysis-eval.md

Each scenario in ``tests/fixtures/analysis/synthetic-gold-v1.json`` (invented
text, not case law, not part of the judgment collection) is run through the
real code and compared with its expected outcome:

- answer scenarios: a scripted provider returns prepared answers to
  ``runs.check_answer`` (the worker's provider call, parsing and validation);
- provider scenarios: the real ``GeminiProvider`` with a scripted SDK client
  (no network; building a real client is refused) classifies failures;
- retry scenarios: attempts are replayed through ``check_answer`` and the
  worker's retry decision (``runs.retry_due``);
- configuration scenarios: ``provider_for`` on explicit settings (``.env`` is
  not read).

The report gives counts per category and lists every mismatch. There is no
pass mark: a mismatch means the code no longer does what the scenario says,
and the exit status is 1. Scenarios marked ``limitation`` show, by design,
what validation cannot catch (they are expected to be *kept*). This measures
LexFlow's checks and error handling, not the quality of any model's legal
analysis, and no model is called. Nothing leaves this computer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

SERVER_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = SERVER_ROOT.parent
FIXTURE = SERVER_ROOT / "tests" / "fixtures" / "analysis" / "synthetic-gold-v1.json"
OUT_DIR = REPO_ROOT / "docs" / "verification" / "phase5"
TEST_URL = "postgresql+psycopg://eval@127.0.0.1:1/lexflow_eval_test"
# Words for operators only: never in a message shown to advocates or clients.
OPERATOR_WORDS = ("GEMINI", "LEXFLOW_", ".env", "API_KEY", "server/", "PROVIDER-ECHO")

os.environ.setdefault("DATABASE_URL", TEST_URL)  # settings need a URL; nothing connects
sys.path.insert(0, str(SERVER_ROOT))

import httpx  # noqa: E402
from google import genai  # noqa: E402
from google.genai import errors  # noqa: E402
from pydantic import SecretStr, ValidationError  # noqa: E402

from lexflow.analysis import runs  # noqa: E402
from lexflow.analysis.evidence import (  # noqa: E402
    CaseContext,
    Evidence,
    JudgmentPassage,
    Passage,
)
from lexflow.analysis.provider import (  # noqa: E402
    GeminiProvider,
    ProviderError,
    Request,
    Response,
    Unavailable,
    provider_for,
)
from lexflow.analysis.validation import (  # noqa: E402
    MODEL_INSUFFICIENT,
    NO_PASSAGES,
    NOTHING_VERIFIED,
)
from lexflow.config import Settings  # noqa: E402

INSUFFICIENT = {
    NO_PASSAGES: "no-passages",
    MODEL_INSUFFICIENT: "model",
    NOTHING_VERIFIED: "nothing-verified",
}


def _refuse_real_client(*args: Any, **kwargs: Any) -> Any:
    raise RuntimeError("the offline evaluation never builds a real Gemini client")


# --- the fixture ----------------------------------------------------------------------


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_evidence(gold: dict[str, Any], override: dict[str, Any] | None = None) -> Evidence:
    case = gold["case"]
    passages = [
        Passage(
            id=p["id"],
            document_id=uuid.UUID(p["document"]),
            document_name=p["document_name"],
            chunk_id=uuid.uuid5(uuid.UUID(p["document"]), str(p["number"])),
            chunk_number=p["number"],
            section_number=p["section"],
            page_number=p["page"],
            text=p["text"],
            content_sha256=_sha(p["text"]),
        )
        for p in gold["passages"]
    ]
    judgments = [
        JudgmentPassage(
            id=j["id"],
            judgment_id=uuid.UUID(j["judgment"]),
            title=j["title"],
            court=j["court"],
            citation=j["citation"],
            year=j["year"],
            synthetic=True,
            rank=rank,
            chunk_id=uuid.uuid5(uuid.UUID(j["judgment"]), str(j["section"])),
            section_number=j["section"],
            page_number=j["page"],
            text=j["text"],
            content_sha256=_sha(j["text"]),
        )
        for rank, j in enumerate(gold["judgments"], start=1)
    ]
    if override and "passages" in override:
        passages = [p for p in passages if p.id in override["passages"]]
    return Evidence(
        context=CaseContext(timeline=[], **case),
        passages=passages,
        judgments=judgments,
        documents_selected=len({p.document_id for p in passages}),
    )


# --- providers --------------------------------------------------------------------------


@dataclass
class ScriptedAnswers:
    """A provider that returns prepared answers in order and counts its calls."""

    answers: list[dict[str, Any]]
    name: str = "scripted"
    model: str = "evaluation-script"
    calls: int = 0

    def generate(self, request: Request) -> Response:
        item = self.answers[self.calls]
        self.calls += 1
        if "raise" in item:
            raise RuntimeError("SCRIPTED-FAULT")  # its text must never be shown
        if "json" in item:
            return Response(text=json.dumps(item["json"]))
        if "fenced" in item:
            return Response(text=f"```json\n{json.dumps(item['fenced'])}\n```")
        if "truncated" in item:
            return Response(text=item["truncated"], truncated=True)
        return Response(text=item["text"])


def _sdk_item(item: dict[str, Any]) -> Any:
    """What the scripted SDK client raises or returns for one fixture item."""
    if "http" in item:
        status = item["http"]
        kind = errors.ServerError if status >= 500 else errors.ClientError
        return kind(status, item["body"])
    if item.get("timeout"):
        return httpx.ReadTimeout("SCRIPTED timeout")
    if item.get("connect"):
        return httpx.ConnectError("SCRIPTED no route")
    spec = item["response"]
    if "candidates" in spec:
        candidates: list[Any] = spec["candidates"]
    else:
        part = SimpleNamespace(text=spec.get("text", "{}"), thought=None)
        candidates = [
            SimpleNamespace(
                content=SimpleNamespace(parts=[part]),
                finish_reason=SimpleNamespace(name=spec.get("finish", "STOP")),
            )
        ]
    block = spec.get("block")
    return SimpleNamespace(
        prompt_feedback=SimpleNamespace(block_reason=block) if block else None,
        candidates=candidates,
        usage_metadata=None,
    )


@dataclass
class ScriptedClient:
    items: list[dict[str, Any]]
    calls: int = 0

    @property
    def models(self) -> ScriptedClient:
        return self

    def generate_content(self, *, model: str, contents: Any, config: Any) -> Any:
        result = _sdk_item(self.items[self.calls])
        self.calls += 1
        if isinstance(result, BaseException):
            raise result
        return result


def scripted_gemini(items: list[dict[str, Any]]) -> tuple[GeminiProvider, ScriptedClient]:
    client = ScriptedClient(items)
    provider = GeminiProvider(
        SecretStr("AIzaFAKE-eval-key-0000000000-not-real"),
        "evaluation-model",
        timeout_seconds=30,
        client_factory=lambda key, timeout_ms: client,
    )
    return provider, client


# --- running scenarios ------------------------------------------------------------------


@dataclass
class Outcome:
    id: str
    category: str
    what: str
    expected: dict[str, Any]
    observed: dict[str, Any]
    limitation: str | None = None
    messages: list[str] = field(default_factory=list)

    @property
    def matches(self) -> bool:
        return self.observed == self.expected

    @property
    def messages_safe(self) -> bool:
        return all(not any(w in m for w in OPERATOR_WORDS) for m in self.messages)


def _summary(outcome: runs.Ready | runs.Failed, calls: int) -> tuple[dict[str, Any], list[str]]:
    if isinstance(outcome, runs.Failed):
        return {"status": "failed", "calls": calls, "code": outcome.code}, [outcome.message]
    result = outcome.result
    reason = result.insufficient_reason
    return (
        {
            "status": "ready",
            "calls": calls,
            "kept": {
                "facts": len(result.facts),
                "issues": len(result.issues),
                "precedents": len(result.precedents),
                "contradictions": len(result.contradictions),
            },
            "removed": {r.code: r.count for r in result.removed.reasons},
            "insufficient": INSUFFICIENT.get(reason or "", reason),
        },
        [r.message for r in result.removed.reasons] + ([reason] if reason else []),
    )


def run_answer(gold: dict[str, Any], s: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    provider = ScriptedAnswers(list(s["answers"]))
    evidence = build_evidence(gold, s.get("evidence"))
    outcome = runs.check_answer(provider, evidence, 4096, label=s["id"])
    return _summary(outcome, provider.calls)


def run_provider(s: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    provider, _ = scripted_gemini([s["item"]])
    request = Request(
        system_instruction="SYNTHETIC",
        prompt="SYNTHETIC",
        response_schema={},
        max_output_tokens=16,
        evidence=Evidence(context=None),  # type: ignore[arg-type]  # not read by the provider
    )
    try:
        response = provider.generate(request)
    except ProviderError as error:
        return {"code": error.code, "retry": error.retry}, [error.message]
    return {"truncated": response.truncated}, []


def run_retry(gold: dict[str, Any], s: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    provider, _ = scripted_gemini(list(s["items"]))
    evidence = build_evidence(gold)
    trail: list[str] = []
    code: str | None = None
    messages: list[str] = []
    for attempt in range(1, s["max_attempts"] + 1):
        outcome = runs.check_answer(provider, evidence, 4096, label=s["id"])
        if isinstance(outcome, runs.Ready):
            trail.append("ready")
            break
        messages.append(outcome.message)
        if runs.retry_due(outcome, attempt, s["max_attempts"]):
            trail.append("queued")
            continue
        trail.append("failed")
        code = outcome.code
        break
    return {"trail": trail, "code": code}, messages


def run_config(s: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
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
        return {"refused": True}, []
    if "force_provider" in s:  # a value that skipped validation
        settings = settings.model_copy(update={"ai_provider": s["force_provider"]})
    provider = provider_for(settings)
    if isinstance(provider, Unavailable):
        return {"unavailable": provider.code}, [provider.reason]
    return {"provider": provider.name}, []


def evaluate(fixture: Path = FIXTURE) -> dict[str, Any]:
    raw = fixture.read_bytes()
    gold = json.loads(raw)
    outcomes: list[Outcome] = []
    for s in gold["scenarios"]:
        kind = s["kind"]
        if kind == "answer":
            observed, messages = run_answer(gold, s)
        elif kind == "provider":
            observed, messages = run_provider(s)
        elif kind == "retry":
            observed, messages = run_retry(gold, s)
        else:
            observed, messages = run_config(s)
        outcomes.append(
            Outcome(
                s["id"],
                s["category"],
                s["what"],
                s["expected"],
                observed,
                s.get("limitation"),
                messages,
            )
        )
    categories: dict[str, Counter[str]] = {}
    for o in outcomes:
        tally = categories.setdefault(o.category, Counter())
        tally["scenarios"] += 1
        tally["as_expected" if o.matches else "not_as_expected"] += 1
    removed: Counter[str] = Counter()
    for o in outcomes:
        removed.update(o.observed.get("removed", {}))
    return {
        "fixture": (
            fixture.relative_to(SERVER_ROOT).as_posix()
            if fixture.is_relative_to(SERVER_ROOT)
            else fixture.name
        ),
        "fixture_sha256": hashlib.sha256(raw).hexdigest(),
        "pipeline": runs.pipeline_record(),
        "scenarios": len(outcomes),
        "as_expected": sum(o.matches for o in outcomes),
        "not_as_expected": [
            {"id": o.id, "expected": o.expected, "observed": o.observed}
            for o in outcomes
            if not o.matches
        ],
        "messages_checked": sum(len(o.messages) for o in outcomes),
        "messages_with_operator_words": [o.id for o in outcomes if not o.messages_safe],
        "by_category": {
            name: {k: tally.get(k, 0) for k in ("scenarios", "as_expected", "not_as_expected")}
            for name, tally in categories.items()
        },
        "removal_reasons_observed": dict(sorted(removed.items())),
        "limitations": [
            {"id": o.id, "kept_as_expected": o.matches, "why": o.limitation}
            for o in outcomes
            if o.limitation
        ],
        "outcomes": [
            {"id": o.id, "category": o.category, "what": o.what, "observed": o.observed}
            for o in outcomes
        ],
    }


def markdown(report: dict[str, Any]) -> str:
    pipeline = report["pipeline"]
    lines = [
        "# AI analysis — offline evaluation (synthetic scenarios)",
        "",
        "Generated by `server/scripts/evaluate_analysis.py --write`. No model is called;",
        "this measures LexFlow's validation and error handling on invented scenarios,",
        "not the quality of any model's legal analysis. There is no pass mark: each",
        "scenario states its expected outcome, and any difference is listed.",
        "",
        f"- Fixture: `server/{report['fixture']}` (SHA-256 `{report['fixture_sha256']}`)",
        f"- Pipeline: prompt `{pipeline['promptVersion']}`, schema "
        f"`{pipeline['schemaVersion']}`, validator `{pipeline['validatorVersion']}`",
        f"- Scenarios: {report['scenarios']}; as expected: {report['as_expected']}; "
        f"not as expected: {len(report['not_as_expected'])}",
        f"- User-facing messages checked: {report['messages_checked']}; containing operator "
        f"words: {len(report['messages_with_operator_words'])}",
        "",
        "| Category | Scenarios | As expected | Not as expected |",
        "|---|---:|---:|---:|",
    ]
    for name, row in report["by_category"].items():
        lines.append(
            f"| {name} | {row['scenarios']} | {row['as_expected']} | {row['not_as_expected']} |"
        )
    lines += ["", "## Removal reasons observed", ""]
    lines += [f"- `{code}`: {n}" for code, n in report["removal_reasons_observed"].items()]
    lines += ["", "## Known limitations (kept by design)", ""]
    lines += [f"- `{item['id']}`: {item['why']}" for item in report["limitations"]]
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
    args = parser.parse_args(argv)
    # Every provider here gets a scripted client; building a real one is refused.
    genai.Client = _refuse_real_client  # type: ignore[assignment,misc]
    report = evaluate()
    text = markdown(report)
    print(text)
    if args.write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "analysis-eval.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
        (OUT_DIR / "analysis-eval.md").write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {OUT_DIR / 'analysis-eval.json'} and analysis-eval.md")
    ok = not report["not_as_expected"] and not report["messages_with_operator_words"]
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
