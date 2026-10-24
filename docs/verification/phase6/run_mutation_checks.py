"""Phase 6 mutation checks: break one review or brief guard at a time and
confirm a test fails.

    server\\.venv\\Scripts\\python docs/verification/phase6/run_mutation_checks.py [--dry-run]

Each check replaces one exact snippet in one source file, runs the tests that
should notice, and restores the file byte for byte (verified) before the next.
A check passes ("caught") when the tests FAIL with the guard removed. The
SHA-256 of every target file is recorded before the run and checked after it,
so the report is valid for uncommitted work too. The tests use only the test
database (``lexflow_test``) and the fake API of the front-end tests. Writes
``mutation-report.md`` and ``mutation-output.log`` next to this script.
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


SERVICE = "server/lexflow/services/reviews.py"
API = "server/lexflow/api/reviews.py"
BRIEF = "server/lexflow/services/brief.py"
AUTHZ = "server/lexflow/authz.py"
TAB = "src/components/workspace/AnalysisTab.tsx"
PANEL = "src/components/workspace/FindingReview.tsx"
R_TESTS = pytest("tests/test_analysis_reviews.py")
B_TESTS = pytest("tests/test_case_brief.py")
UI_TESTS = vitest("src/pages/review.test.tsx")

MUTATIONS = [
    # --- decisions and history ------------------------------------------------------------
    Mutation(
        "P6-1",
        "a stale version is refused",
        SERVICE,
        "    if expected_version != version:",
        "    if False:",
        R_TESTS,
    ),
    Mutation(
        "P6-2",
        "a change that alters nothing adds no history entry",
        SERVICE,
        "    if change == before:\n        return Outcome(review, changed=False)",
        "    if False:\n        return Outcome(review, changed=False)",
        R_TESTS,
    ),
    Mutation(
        "P6-3",
        "an edit must change the AI's wording",
        API,
        '        if _SPACE.sub(" ", wording) == _SPACE.sub(" ", item.text.strip()):',
        "        if False:",
        R_TESTS,
    ),
    Mutation(
        "P6-4",
        "a not-ready run cannot be reviewed",
        API,
        '    if run.status != "ready" or run.result is None:',
        "    if False:",
        R_TESTS,
    ),
    Mutation(
        "P6-5",
        "a run of another case is not found through this case",
        API,
        "    if run is None or run.case_id != case.id:",
        "    if run is None:",
        R_TESTS,
    ),
    Mutation(
        "P6-6",
        "a finding must exist in the run",
        API,
        '    if found is None:\n        raise ProblemError(404, "finding-not-found", FINDING_NOT_FOUND)',
        '    if False:\n        raise ProblemError(404, "finding-not-found", FINDING_NOT_FOUND)',
        R_TESTS,
    ),
    # --- who may do what ----------------------------------------------------------------------
    Mutation(
        "P6-7",
        "paralegals may not decide on findings",
        AUTHZ,
        "    Action.REVIEW_ANALYSIS: _ADVOCATES_ON_CASE,",
        "    Action.REVIEW_ANALYSIS: _STAFF_ON_CASE,",
        R_TESTS,
    ),
    Mutation(
        "P6-8",
        "notes are shown to reviewers only",
        API,
        "def may_see_notes(rel: Relation) -> bool:\n    return authz.allows(rel, Action.REVIEW_ANALYSIS)",
        "def may_see_notes(rel: Relation) -> bool:\n    return True",
        R_TESTS,
    ),
    # --- audit and timeline carry no content --------------------------------------------------
    Mutation(
        "P6-9",
        "the audit event holds no note",
        API,
        '                "noteChanged": outcome.note_changed,',
        '                "noteChanged": outcome.note_changed,\n                "note": change.note,',
        R_TESTS,
    ),
    Mutation(
        "P6-10",
        "the timeline entry holds no note",
        SERVICE,
        'description=f"{name} of the AI analysis of {run_day} {_VERB[event.status]}.",',
        'description=f"{name} of the AI analysis of {run_day} {_VERB[event.status]}. {event.note}",',
        R_TESTS,
    ),
    # --- the brief ------------------------------------------------------------------------------
    Mutation(
        "P6-11",
        "the brief holds only accepted findings",
        BRIEF,
        "    accepted = {f.id for f in items if f.id in reviews and reviews[f.id].status in ACCEPTED}",
        "    accepted = {f.id for f in items if f.id in reviews}",
        B_TESTS,
    ),
    Mutation(
        "P6-12",
        "an edited finding appears in the lawyer's wording",
        BRIEF,
        '            text = review.reviewed_text if review.status == "edited" else finding.text',
        "            text = finding.text",
        B_TESTS,
    ),
    Mutation(
        "P6-13",
        "synthetic judgments are labelled in the brief",
        BRIEF,
        '        if item.get("synthetic"):\n            w.line(SYNTHETIC_LABEL, italic=True)',
        "        if False:\n            w.line(SYNTHETIC_LABEL, italic=True)",
        B_TESTS,
    ),
    Mutation(
        "P6-14",
        "changed sources are flagged in the brief",
        BRIEF,
        '            if source.get("evidenceId") in changed:',
        "            if False:",
        B_TESTS,
    ),
    Mutation(
        "P6-15",
        "no brief without an accepted finding",
        API,
        "    if tally.included == 0:",
        "    if False:",
        B_TESTS,
    ),
    # --- the UI -------------------------------------------------------------------------------
    Mutation(
        "U6-1",
        "review controls only for those the server allows",
        TAB,
        "  const canReview = reviews.data?.canReview ?? false;",
        "  const canReview = true;",
        UI_TESTS,
    ),
    Mutation(
        "U6-2",
        "unreviewed findings are visibly marked",
        PANEL,
        "    label: 'Unreviewed',",
        "    label: '',",
        UI_TESTS,
    ),
    Mutation(
        "U6-3",
        "the export needs an accepted finding",
        PANEL,
        "        disabled={included === 0 || exportBrief.isPending}",
        "        disabled={exportBrief.isPending}",
        UI_TESTS,
    ),
    Mutation(
        "U6-4",
        "review decisions are not counted as analysis input",
        TAB,
        "  const caseEvents = c.timeline.filter((e) => e.kind !== 'review').length;",
        "  const caseEvents = c.timeline.length;",
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
        f"Phase 6 mutation checks on the working tree of {head}, {started:%Y-%m-%d %H:%M} UTC",
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
            line
            for line in plain(result.stdout + result.stderr).splitlines()
            if line.strip()
        ]
        log += [f"=== {m.id} {verdict}: {m.label}", f"file: {m.path}", *tail[-10:], ""]
    if snapshot(targets) != before:
        print("Target files differ from their state before the run; stopping.")
        return 5
    caught = sum(1 for _, code in rows if code != 0)
    report = [
        "# Phase 6 mutation checks",
        "",
        (
            f"Working tree on commit `{head}`; run {started:%Y-%m-%d %H:%M} UTC; script "
            "`docs/verification/phase6/run_mutation_checks.py` (raw output: `mutation-output.log`)."
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
    (HERE / "mutation-output.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    print(f"{caught} of {len(rows)} caught; all files restored.")
    return 0 if caught == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
