"""Phase 5 mutation checks: break one guard at a time and confirm a test fails.

    server\\.venv\\Scripts\\python docs/verification/phase5/run_mutation_checks.py

Each check replaces one exact snippet in one source file, runs the tests that
should notice, and restores the file byte-for-byte (verified) before the next.
A check passes ("caught") when the tests FAIL with the guard removed.

The tests use only the test database (``lexflow_test`` via ``TEST_DATABASE_URL``,
which must point at a PostgreSQL server with pgvector) and the fake API of the
front-end tests. Refuses to start if any
target file has uncommitted changes. Writes, next to this script:
``mutation-report.md`` (table and commands) and ``mutation-output.log`` (the
tail of each test run).
"""

from __future__ import annotations

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


VALIDATION = "server/lexflow/analysis/validation.py"
OUTPUT = "server/lexflow/analysis/output.py"
PROVIDER = "server/lexflow/analysis/provider.py"
RUNS = "server/lexflow/analysis/runs.py"
EVIDENCE = "server/lexflow/analysis/evidence.py"
API = "server/lexflow/api/analysis.py"
TAB = "src/components/workspace/AnalysisTab.tsx"
V_TESTS = pytest("tests/test_analysis_validation.py")
O_TESTS = pytest("tests/test_analysis_output.py")
P_TESTS = pytest("tests/test_analysis_provider.py")
C_TESTS = pytest("tests/test_analysis_config.py", "tests/test_analysis_provider.py")
E_TESTS = pytest("tests/test_analysis_evidence.py")
R_TESTS = pytest("tests/test_analysis_runs.py")
UI_TESTS = vitest("src/pages/analysis.test.tsx")

MUTATIONS = [
    # --- validation: only verifiable items survive -----------------------------------------
    Mutation(
        "V-1",
        "a quote must occur in the passage it cites",
        VALIDATION,
        "        if wanted not in self._normal[passage.id]:",
        "        if False:",
        V_TESTS,
    ),
    Mutation(
        "V-2",
        "a fact citing an unknown passage is removed (not re-pointed)",
        VALIDATION,
        "self.evidence.passage(evidence_id) if EVIDENCE_ID.fullmatch(evidence_id) else None",
        "self.evidence.passage(evidence_id) or (self.evidence.passages or [None])[0]",
        V_TESTS,
    ),
    Mutation(
        "V-3",
        "an output citing an unknown judgment is rejected",
        VALIDATION,
        "        passage = evidence.judgment(item.evidence) if EVIDENCE_ID.fullmatch(item.evidence) else None",
        "        passage = evidence.judgment(item.evidence) or (evidence.judgments or [None])[0]",
        V_TESTS,
    ),
    Mutation(
        "V-4",
        "very short quotes cannot support a fact",
        VALIDATION,
        "        if len(wanted) < QUOTE_MIN:",
        "        if False:",
        V_TESTS,
    ),
    Mutation(
        "V-5",
        "issues keep only references to surviving facts",
        VALIDATION,
        "refs = list(dict.fromkeys(i for i in issue.fact_ids if i in kept_ids))",
        "refs = list(dict.fromkeys(issue.fact_ids))",
        V_TESTS,
    ),
    Mutation(
        "V-6",
        "a contradiction needs two verified sources",
        VALIDATION,
        "        if len(sources) < 2:",
        "        if len(sources) < 1:",
        V_TESTS,
    ),
    Mutation(
        "V-7",
        "invented law-report citations are removed",
        VALIDATION,
        "                if match.group(0) not in self._known_text:",
        "                if False:",
        V_TESTS,
    ),
    Mutation(
        "V-8",
        "a returned outcome assessment is counted as removed",
        VALIDATION,
        '    if parsed.outcome_discarded:\n        tally.remove("outcome-discarded")',
        '    if False:\n        tally.remove("outcome-discarded")',
        V_TESTS,
    ),
    Mutation(
        "V-9",
        "precedent titles come from the collection, not the model",
        VALIDATION,
        "                title=passage.title,",
        "                title=item.summary,",
        V_TESTS,
    ),
    Mutation(
        "V-10",
        "nothing verifiable means insufficient evidence",
        VALIDATION,
        "    elif not facts and not precedents and not contradictions:",
        "    elif False:",
        V_TESTS,
    ),
    # --- the model's answer is parsed defensively ------------------------------------------
    Mutation(
        "O-1",
        "the answer must be a JSON object",
        OUTPUT,
        "    if not isinstance(data, dict):",
        "    if False:",
        O_TESTS,
    ),
    Mutation(
        "O-2",
        "outcome keys are noticed",
        OUTPUT,
        "    out.outcome_discarded = any(key in data for key in OUTCOME_KEYS)",
        "    out.outcome_discarded = False",
        O_TESTS,
    ),
    # --- the provider: no leaks, no hidden retries -----------------------------------------
    Mutation(
        "P-1",
        "provider error text is never passed on",
        PROVIDER,
        "            raise _api_error(exc.code) from None",
        '            raise ProviderError("provider-error", str(exc), retry=True) from None',
        P_TESTS,
    ),
    Mutation(
        "P-2",
        "the SDK makes no retries of its own",
        PROVIDER,
        "types.HttpOptions(timeout=timeout_ms, retry_options=None)",
        "types.HttpOptions(timeout=timeout_ms, retry_options=types.HttpRetryOptions())",
        P_TESTS,
    ),
    Mutation(
        "P-3",
        "the timeout is given in milliseconds",
        PROVIDER,
        "        self._timeout_ms = timeout_seconds * 1000",
        "        self._timeout_ms = timeout_seconds",
        P_TESTS,
    ),
    Mutation(
        "P-4",
        "blocked answers fail",
        PROVIDER,
        "    if finish in _BLOCKED_FINISH:",
        "    if False:",
        P_TESTS,
    ),
    Mutation(
        "P-5",
        "a cut-off answer is marked truncated",
        PROVIDER,
        'truncated=finish == "MAX_TOKENS"',
        "truncated=False",
        P_TESTS,
    ),
    # --- configuration ---------------------------------------------------------------------
    Mutation(
        "C-1",
        "the scripted double is refused outside test/e2e databases",
        "server/lexflow/config.py",
        '            self.env in ("test", "development") and _is_test_database(self.database_url)',
        "            True",
        C_TESTS,
    ),
    Mutation(
        "C-2",
        "a blank key counts as missing",
        "server/lexflow/config.py",
        "        if value is None or not value.get_secret_value().strip():",
        "        if value is None:",
        C_TESTS,
    ),
    Mutation(
        "C-3",
        "a missing key is reported by name",
        PROVIDER,
        "        if settings.gemini_api_key is None:",
        "        if False:",
        C_TESTS,
    ),
    # --- evidence ----------------------------------------------------------------------------
    Mutation(
        "E-1",
        "evidence comes only from the case's own documents",
        EVIDENCE,
        "            Document.case_id == case_id,\n            Document.id.in_(document_ids),",
        "            Document.id.in_(document_ids),",
        E_TESTS,
    ),
    Mutation(
        "E-2",
        "deleted documents are never evidence",
        EVIDENCE,
        "            Document.id.in_(document_ids),\n            Document.deleted_at.is_(None),",
        "            Document.id.in_(document_ids),",
        E_TESTS,
    ),
    # --- runs: access, gates, limits, queue, audit -----------------------------------------
    Mutation(
        "R-1",
        "only advocates on the case and administrators start runs",
        "server/lexflow/authz.py",
        "    Action.RUN_ANALYSIS: _ADVOCATES_ON_CASE,",
        "    Action.RUN_ANALYSIS: _STAFF_ON_CASE,",
        R_TESTS,
    ),
    Mutation(
        "R-2",
        "the user must confirm the transmission",
        API,
        "    if not body.confirm_transmission:",
        "    if False:",
        R_TESTS,
    ),
    Mutation(
        "R-3",
        "only sample cases are accepted unless client data is allowed (API)",
        API,
        "    if not settings.ai_allow_client_data and not case.is_sample:",
        "    if False:",
        R_TESTS,
    ),
    Mutation(
        "R-4",
        "the worker re-checks the sample-case gate before sending",
        RUNS,
        "    if not case.is_sample and not settings.ai_allow_client_data:",
        "    if False:",
        R_TESTS,
    ),
    Mutation(
        "R-5",
        "only ready documents of this case may be selected",
        API,
        "    if len(eligible) != len(document_ids):",
        "    if False:",
        R_TESTS,
    ),
    Mutation(
        "R-6",
        "the hourly limit per person",
        API,
        "        >= settings.ai_runs_per_user_per_hour",
        "        >= 1_000_000",
        R_TESTS,
    ),
    Mutation(
        "R-7",
        "a result is stored only by the worker holding the run",
        RUNS,
        '    if run is None or run.status != "running" or run.worker_id != worker_id:',
        "    if run is None:",
        R_TESTS,
    ),
    Mutation(
        "R-8",
        "starting a run is audited",
        API,
        '    audit.record(\n        "analysis.requested",',
        '    (lambda *a, **k: None)(\n        "analysis.requested",',
        R_TESTS,
    ),
    Mutation(
        "R-9",
        "a run is read only through its own case",
        API,
        "    if run is None or run.case_id != case.id:",
        "    if run is None:",
        R_TESTS,
    ),
    Mutation(
        "R-10",
        "a busy provider is retried only after a pause",
        RUNS,
        "            run.available_at = now + timedelta(seconds=RETRY_PAUSE_SECONDS * run.attempts)",
        "            run.available_at = now",
        R_TESTS,
    ),
    Mutation(
        "R-11",
        "no provider call when there is no text",
        RUNS,
        "    if not evidence.passages:\n        return Ready(",
        "    if False:\n        return Ready(",
        R_TESTS,
    ),
    Mutation(
        "R-12",
        "the worker skips analysis without migration 0011",
        "server/lexflow/worker.py",
        "        if not analysis_runs.table_exists(session):",
        "        if False:",
        R_TESTS,
    ),
    # --- the UI ------------------------------------------------------------------------------
    Mutation(
        "U-1",
        "nothing is sent without explicit confirmation",
        TAB,
        "  else if (!blocked && !confirmed) blocked = 'Confirm what will be sent before starting.';\n",
        "",
        UI_TESTS,
    ),
    Mutation(
        "U-2",
        "a run of another case is never shown",
        "src/hooks/useCaseAnalysis.ts",
        "      if (run.caseId !== caseId || run.id !== runId) {",
        "      if (run.id !== runId) {",
        UI_TESTS,
    ),
    Mutation(
        "U-3",
        "fact links open the cited page",
        TAB,
        "        to={documentTextPath(caseId, source.documentId, source.sectionNumber)}",
        "        to={documentTextPath(caseId, source.documentId)}",
        UI_TESTS,
    ),
    Mutation(
        "U-4",
        "the disclaimer is shown with every result",
        TAB,
        "              </ul>\n            </div>\n          )}\n          <DecisionSupportNote />\n",
        "              </ul>\n            </div>\n          )}\n",
        UI_TESTS,
    ),
    Mutation(
        "U-5",
        "documents without text cannot be chosen",
        TAB,
        "                    disabled={!d.eligible}",
        "                    disabled={false}",
        UI_TESTS,
    ),
    Mutation(
        "U-6",
        "no precedents available is said plainly",
        TAB,
        "          {!result.precedentsAvailable ? (",
        "          {false ? (",
        UI_TESTS,
    ),
]


def git_status(paths: list[str]) -> str:
    return subprocess.run(
        ["git", "status", "--porcelain", "--", *paths],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


REDACTIONS = [
    # Home folders (any slash style, including escaped backslashes) and pytest's
    # per-user temp folder name the local account.
    (re.compile(r"[A-Za-z]:(?:\\\\|\\|/)Users(?:\\\\|\\|/)[^\\/'\"\s]+"), "<home>"),
    (re.compile(r"pytest-of-[^\\/'\"\s]+"), "pytest-of-<user>"),
    # Database URLs: the role name (the password is already masked by SQLAlchemy).
    (re.compile(r"(postgresql(?:\+\w+)?://)[^:@/\s]+(?::[^@\s]*)?@"), r"\1<user>:***@"),
    # Row ids printed by failing assertions (rows of the throwaway test database).
    (
        re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),
        "<uuid>",
    ),
]


def plain(output: str) -> str:
    """Test output without terminal colour codes, local paths, database roles or row ids."""
    output = re.sub(r"\x1b\[[0-9;]*m", "", output)
    for pattern, replacement in REDACTIONS:
        output = pattern.sub(replacement, output)
    return output


def failures(output: str) -> list[str]:
    marks = ("FAILED ", " FAIL ", "×")
    return [
        line.strip() for line in output.splitlines() if any(m in line for m in marks)
    ][:8]


def dry_run() -> int:
    """Check that every snippet occurs exactly once; change nothing."""
    bad = 0
    for m in MUTATIONS:
        text = (ROOT / m.path).read_text(encoding="utf-8")
        crlf = "\r\n" in text  # the working copy may use CRLF (git autocrlf)
        old = m.old.replace("\n", "\r\n") if crlf else m.old
        if text.count(old) != 1:
            print(f"{m.id}: snippet found {text.count(old)} times in {m.path}")
            bad += 1
    print(f"{len(MUTATIONS) - bad} of {len(MUTATIONS)} snippets found exactly once.")
    return 1 if bad else 0


def main() -> int:
    if sys.argv[1:] == ["--dry-run"]:
        return dry_run()
    targets = sorted({m.path for m in MUTATIONS})
    if git_status(targets):
        print(
            "Refusing: a target file has uncommitted changes:\n" + git_status(targets)
        )
        return 2
    head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    started = datetime.now(UTC)
    rows: list[tuple[Mutation, int, float, list[str]]] = []
    log = [
        f"Phase 5 mutation checks at commit {head}, started {started:%Y-%m-%d %H:%M:%S} UTC",
        "Redacted: local home paths, database role names and row ids (see REDACTIONS).",
        "",
    ]

    for m in MUTATIONS:
        path = ROOT / m.path
        original = path.read_bytes()
        text = original.decode("utf-8")
        old, new = m.old, m.new
        if "\r\n" in text:  # the working copy may use CRLF (git autocrlf)
            old, new = old.replace("\n", "\r\n"), new.replace("\n", "\r\n")
        if text.count(old) != 1:
            print(
                f"{m.id}: snippet found {text.count(old)} times in {m.path}; stopping."
            )
            return 3
        command, cwd = m.run
        path.write_bytes(text.replace(old, new).encode("utf-8"))
        begun = time.monotonic()
        try:
            result = subprocess.run(
                command,
                check=False,  # a failing run is the expected outcome
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
        seconds = time.monotonic() - begun
        output = plain(result.stdout + result.stderr)
        verdict = "CAUGHT" if result.returncode != 0 else "SURVIVED"
        rows.append((m, result.returncode, seconds, failures(output)))
        print(f"{m.id} {verdict} (exit {result.returncode}, {seconds:.0f}s): {m.label}")
        tail = [line for line in output.splitlines() if line.strip()][-12:]
        log += [
            f"=== {m.id} {verdict}: {m.label}",
            f"file: {m.path}",
            f"command (cwd {cwd.relative_to(ROOT) or '.'}): {command.replace(PY, 'server/.venv/Scripts/python.exe')}",
            f"exit code: {result.returncode}",
            *tail,
            "",
        ]

    if git_status(targets):
        print(
            "Target files differ from the commit after the run:\n" + git_status(targets)
        )
        return 5

    caught = sum(1 for _, code, _, _ in rows if code != 0)
    report = [
        "# Phase 5 mutation checks",
        "",
        (
            f"Commit `{head}`; run {started:%Y-%m-%d %H:%M} UTC; script "
            "`docs/verification/phase5/run_mutation_checks.py` (raw output: "
            "`mutation-output.log`)."
        ),
        "",
        (
            "Each row removes or weakens one guard, runs the listed tests, and restores the "
            "file byte-for-byte (checked after every row, and `git status` of every target "
            "file checked clean at the end). **Caught** = the tests failed with the guard "
            "removed."
        ),
        "",
        f"**Result: {caught} of {len(rows)} caught.**",
        "",
        "| ID | Guard | File | Tests run | Exit | Result |",
        "|---|---|---|---|---|---|",
    ]
    for m, code, _, _ in rows:
        tests = " ".join(
            part for part in m.run[0].split() if part.startswith(("tests/", "src/"))
        )
        report.append(
            f"| {m.id} | {m.label} | `{m.path}` | `{tests}` | {code} | "
            f"{'caught' if code != 0 else '**survived**'} |"
        )
    report += ["", "## Failing tests per check", ""]
    for m, _, _, failed in rows:
        report.append(
            f"- **{m.id}**: " + ("; ".join(f"`{f}`" for f in failed) or "(none listed)")
        )
    (HERE / "mutation-report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    (HERE / "mutation-output.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    print(f"{caught} of {len(rows)} caught; all files restored.")
    return 0 if caught == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
