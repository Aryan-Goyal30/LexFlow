"""Phase 7 mutation checks: break one outcome-assessment guard at a time and
confirm a test fails.

    server\\.venv\\Scripts\\python docs/verification/phase7/run_mutation_checks.py [--dry-run]

The same method as Phase 6 (``docs/verification/phase6/run_mutation_checks.py``):
each check replaces one exact snippet in one source file, runs the tests that
should notice, and restores the file byte for byte (verified) before the next.
A check passes ("caught") when the tests FAIL with the guard removed. The
tests use only the test database (``lexflow_test``) and the fake API of the
front-end tests; no model is called. Writes ``mutation-report.md`` and
``mutation-output.log`` next to this script.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SERVER = ROOT / "server"
PY = str(SERVER / ".venv" / "Scripts" / "python.exe")


def pytest(*files: str) -> tuple[str, Path]:
    return f'"{PY}" -m pytest -q -p no:cacheprovider ' + " ".join(files), SERVER


def vitest(*files: str) -> tuple[str, Path]:
    return "npx vitest run " + " ".join(files), ROOT


@dataclass(frozen=True)
class Mutation:
    id: str
    label: str
    path: str
    old: str
    new: str
    run: tuple[str, Path]


VALIDATION = "server/lexflow/assessment/validation.py"
OUTPUT = "server/lexflow/assessment/output.py"
INPUTS = "server/lexflow/assessment/inputs.py"
SERVICE = "server/lexflow/assessment/service.py"
API = "server/lexflow/api/assessments.py"
REVIEWS_API = "server/lexflow/api/reviews.py"
CONFIG = "server/lexflow/config.py"
AUTHZ = "server/lexflow/authz.py"
TAB = "src/components/workspace/AnalysisTab.tsx"
PANEL = "src/components/workspace/OutcomeAssessment.tsx"
V_TESTS = pytest("tests/test_assessment_validation.py")
A_TESTS = pytest("tests/test_assessments_api.py")
UI_TESTS = vitest("src/pages/assessment.test.tsx")


def m(id_: str, label: str, path: str, old: str, new: str, run: tuple[str, Path]) -> Mutation:
    return Mutation(id_, label, path, old, new, run)


MUTATIONS = [
    # --- validation (P7-A2, P7-A3) ---------------------------------------------------------
    m(
        "P7-1",
        "a cited precedent must be an accepted comparison of the run",
        VALIDATION,
        "inputs.precedent(item.precedent) if PRECEDENT_REF.fullmatch(item.precedent) else None",
        "inputs.precedents[0] if inputs.precedents else None",
        V_TESTS,
    ),
    m(
        "P7-2",
        "a quote must occur in the cited judgment passage",
        VALIDATION,
        "        if _find_in_order(normalise(precedent.text), pieces) is None:",
        "        if False:",
        V_TESTS,
    ),
    m(
        "P7-3",
        "a reasoning step may rest only on accepted findings",
        VALIDATION,
        "            and all(FINDING_REF.fullmatch(f) and f in accepted for f in findings)",
        "            and True",
        V_TESTS,
    ),
    m(
        "P7-4",
        "probability and percentage wording is rejected",
        VALIDATION,
        "            if _PROBABILITY.search(plain):",
        "            if False:",
        V_TESTS,
    ),
    m(
        "P7-5",
        "outcome predictions and definitive claims are rejected",
        VALIDATION,
        "            if _OUTCOME.search(plain) or _DEFINITIVE.search(plain):",
        "            if False:",
        V_TESTS,
    ),
    m(
        "P7-6",
        "a synthetic judgment may not be called real law",
        VALIDATION,
        "            if self._synthetic and _CALLED_REAL.search(plain):",
        "            if False:",
        V_TESTS,
    ),
    m(
        "P7-7",
        "a forbidden summary withholds the whole assessment",
        VALIDATION,
        "    prose = check.prose(parsed.summary)",
        "    prose = None",
        V_TESTS,
    ),
    m(
        "P7-8",
        "no assessment without a verified precedent",
        VALIDATION,
        "    if not cited:",
        "    if False:",
        V_TESTS,
    ),
    m(
        "P7-9",
        "the uncertainty category must fit the cited stances",
        VALIDATION,
        "    uncertainty = _consistent(parsed.uncertainty, [c.stance for c in cited])",
        "    uncertainty = parsed.uncertainty",
        V_TESTS,
    ),
    m(
        "P7-10",
        "the synthetic flag comes from the collection, not the answer",
        VALIDATION,
        "                synthetic=precedent.synthetic,",
        "                synthetic=False,",
        V_TESTS,
    ),
    m(
        "P7-11",
        "fields outside the contract (scores, relabelling) are counted",
        OUTPUT,
        "    out.unexpected_fields = sum(1 for key in data if key not in KNOWN_KEYS)",
        "    out.unexpected_fields = 0",
        V_TESTS,
    ),
    # --- inputs and gate (P7-A5) -----------------------------------------------------------
    m(
        "P7-12",
        "rejected and unreviewed findings never reach the provider",
        INPUTS,
        "        if status not in ACCEPTED or review is None:",
        "        if review is None:",
        A_TESTS,
    ),
    m(
        "P7-13",
        "a changed judgment passage cannot support an assessment",
        INPUTS,
        "        if chunk.content_sha256 != expected:",
        "        if False:",
        A_TESTS,
    ),
    m(
        "P7-14",
        "no accepted finding: no provider call",
        INPUTS,
        "        if not self.findings:",
        "        if False:",
        A_TESTS,
    ),
    # --- API, review, brief, flag, roles (P7-A1, P7-A4, P7-A6, P7-A7) -----------------------
    m(
        "P7-15",
        "with the flag off every route answers 404",
        API,
        "    if not assessment_enabled(settings, session):",
        "    if False:",
        A_TESTS,
    ),
    m(
        "P7-16",
        "only a ready assessment can be reviewed",
        API,
        '    if assessment.status != "ready" or assessment.result is None:',
        "    if False:",
        A_TESTS,
    ),
    m(
        "P7-17",
        "a stale review version is refused",
        SERVICE,
        "    if expected_version != version:",
        "    if False:",
        A_TESTS,
    ),
    m(
        "P7-18",
        "reviewers' notes are hidden from paralegals",
        API,
        "        note=review.note if notes else None,",
        "        note=review.note,",
        A_TESTS,
    ),
    m(
        "P7-19",
        "only an accepted assessment reaches the brief",
        SERVICE,
        "            OutcomeAssessmentReview.status.in_(tuple(inputs_mod.ACCEPTED)),",
        '            OutcomeAssessmentReview.status.in_(("accepted", "edited", "rejected")),',
        A_TESTS,
    ),
    m(
        "P7-20",
        "with the flag off the brief has no assessment",
        REVIEWS_API,
        "        assessment_service.accepted_for_brief(session, run.id) if assessments_on else None",
        "        assessment_service.accepted_for_brief(session, run.id)",
        A_TESTS,
    ),
    m(
        "P7-21",
        "the flag is refused outside a test or e2e database",
        CONFIG,
        "        if self.outcome_assessment and not (",
        "        if False and self.outcome_assessment and not (",
        A_TESTS,
    ),
    m(
        "P7-22",
        "only advocates on the case and administrators generate",
        AUTHZ,
        "    Action.RUN_ASSESSMENT: _ADVOCATES_ON_CASE,",
        "    Action.RUN_ASSESSMENT: _STAFF_ON_CASE,",
        A_TESTS,
    ),
    # --- UI (P7-A1, P7-A4) -----------------------------------------------------------------
    m(
        "U7-1",
        "the card appears only when the server enables the feature",
        TAB,
        "      {assessmentEnabled && <AssessmentPanel caseId={caseId} runId={run.id} />}",
        "      {<AssessmentPanel caseId={caseId} runId={run.id} />}",
        UI_TESTS,
    ),
    m(
        "U7-2",
        "synthetic or scripted output carries the demonstration banner",
        PANEL,
        "      {r.demoOnly && (",
        "      {false && (",
        UI_TESTS,
    ),
    m(
        "U7-3",
        "review controls only for those who may review",
        PANEL,
        "      {canReview && mode === 'idle' && (",
        "      {mode === 'idle' && (",
        UI_TESTS,
    ),
]

REDACTIONS = [
    (re.compile(r"[A-Za-z]:(?:\\\\|\\|/)Users(?:\\\\|\\|/)[^\\/'\"\s]+"), "<home>"),
    (re.compile(r"pytest-of-[^\\/'\"\s]+"), "pytest-of-<user>"),
    (re.compile(r"(postgresql(?:\+\w+)?://)[^:@/\s]+(?::[^@\s]*)?@"), r"\1<user>:***@"),
    (
        re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),
        "<uuid>",
    ),
]


def plain(output: str) -> str:
    output = re.sub(r"\x1b\[[0-9;]*m", "", output)
    for pattern, replacement in REDACTIONS:
        output = pattern.sub(replacement, output)
    return output


def snippet(text: str, value: str) -> str:
    return value.replace("\n", "\r\n") if "\r\n" in text else value


def snapshot(paths: list[str]) -> dict[str, str]:
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}


def dry_run() -> int:
    bad = 0
    for m in MUTATIONS:
        text = (ROOT / m.path).read_text(encoding="utf-8")
        found = text.count(snippet(text, m.old))
        if found != 1:
            print(f"{m.id}: snippet found {found} times in {m.path}")
            bad += 1
    print(f"{len(MUTATIONS) - bad} of {len(MUTATIONS)} snippets found exactly once.")
    return 1 if bad else 0


def main() -> int:
    if sys.argv[1:] == ["--dry-run"]:
        return dry_run()
    targets = sorted({m.path for m in MUTATIONS})
    before = snapshot(targets)
    head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    started = datetime.now(UTC)
    rows: list[tuple[Mutation, int]] = []
    log = [
        f"Phase 7 mutation checks on the working tree of {head}, {started:%Y-%m-%d %H:%M} UTC",
        "",
    ]
    for m in MUTATIONS:
        path = ROOT / m.path
        original = path.read_bytes()
        text = original.decode("utf-8")
        old, new = snippet(text, m.old), snippet(text, m.new)
        if text.count(old) != 1:
            print(f"{m.id}: snippet not found exactly once in {m.path}; stopping.")
            return 3
        command, cwd = m.run
        path.write_bytes(text.replace(old, new).encode("utf-8"))
        begun = time.monotonic()
        try:
            result = subprocess.run(
                command,
                check=False,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        finally:
            path.write_bytes(original)
        if path.read_bytes() != original:
            print(f"{m.id}: {m.path} was not restored exactly; stopping.")
            return 4
        verdict = "CAUGHT" if result.returncode != 0 else "SURVIVED"
        rows.append((m, result.returncode))
        print(
            f"{m.id} {verdict} (exit {result.returncode}, {time.monotonic() - begun:.0f}s): {m.label}"
        )
        tail = [
            line.rstrip()  # no trailing spaces in the saved log (git diff --check)
            for line in plain(result.stdout + result.stderr).splitlines()
            if line.strip()
        ]
        log += [f"=== {m.id} {verdict}: {m.label}", f"file: {m.path}", *tail[-10:], ""]
    if snapshot(targets) != before:
        print("Target files differ from their state before the run; stopping.")
        return 5
    caught = sum(1 for _, code in rows if code != 0)
    report = [
        "# Phase 7 mutation checks (outcome assessment demo)",
        "",
        (
            f"Working tree on commit `{head}`; run {started:%Y-%m-%d %H:%M} UTC; script "
            "`docs/verification/phase7/run_mutation_checks.py` (raw output: `mutation-output.log`)."
        ),
        "",
        (
            "Each row removes or weakens one guard, runs the listed tests and restores the file "
            "byte for byte (checked after every row; every target's SHA-256 is unchanged at the "
            "end). **Caught** = the tests failed with the guard removed."
        ),
        "",
        f"**Result: {caught} of {len(rows)} caught.**",
        "",
        "| ID | Guard | File | Tests | Exit | Result |",
        "|---|---|---|---|---|---|",
    ]
    for m, code in rows:
        tests = " ".join(
            p for p in m.run[0].split() if p.startswith(("tests/", "src/"))
        )
        result_text = "caught" if code != 0 else "**survived**"
        report.append(
            f"| {m.id} | {m.label} | `{m.path}` | `{tests}` | {code} | {result_text} |"
        )
    report += ["", "## Target files (SHA-256, unchanged before and after)", ""]
    report += [f"- `{p}` `{digest}`" for p, digest in before.items()]
    (HERE / "mutation-report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    (HERE / "mutation-output.log").write_text("\n".join(log).rstrip() + "\n", encoding="utf-8")
    print(f"{caught} of {len(rows)} caught; all files restored.")
    return 0 if caught == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
