"""Phase 4 mutation checks: break one guard at a time and confirm a test fails.

    server\\.venv\\Scripts\\python docs/verification/phase4/run_mutation_checks.py

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


IMPORT = "server/lexflow/services/judgment_import.py"
CLI = "server/lexflow/cli/judgments.py"
API = "server/lexflow/api/judgments.py"
SERVICE = "server/lexflow/services/judgments.py"
UI = "src/components/research/Judgments.tsx"
IMPORT_TESTS = pytest("tests/test_judgment_import.py")
API_TESTS = pytest("tests/test_judgments_api.py")
UI_TESTS = vitest("src/pages/research.test.tsx")

MUTATIONS = [
    # --- ingestion: provenance, validation, synthetic data -----------------------------------
    Mutation(
        "I-1",
        "synthetic sources need --allow-synthetic",
        CLI,
        "        if not args.allow_synthetic:",
        "        if False:",
        IMPORT_TESTS,
    ),
    Mutation(
        "I-2",
        "synthetic data never enters a non-test database",
        CLI,
        '        if "test" not in database and "e2e" not in database:',
        "        if False:",
        IMPORT_TESTS,
    ),
    Mutation(
        "I-3",
        "files cannot leave the manifest's folder",
        IMPORT,
        "    if not candidate.is_relative_to(folder):",
        "    if False:",
        IMPORT_TESTS,
    ),
    Mutation(
        "I-4",
        "addresses must be https",
        IMPORT,
        '        parts.scheme != "https"',
        '        parts.scheme not in ("https", "http")',
        IMPORT_TESTS,
    ),
    Mutation(
        "I-5",
        "synthetic sources use reserved .invalid addresses",
        IMPORT,
        '    if synthetic is True and not host.endswith(".invalid"):',
        "    if False:",
        IMPORT_TESTS,
    ),
    Mutation(
        "I-6",
        "a file already in the collection is a duplicate",
        IMPORT,
        "        elif same_content is not None:",
        "        elif False:",
        IMPORT_TESTS,
    ),
    Mutation(
        "I-7",
        "a citation already in the collection is a duplicate",
        IMPORT,
        '            if other is not None:\n                item.status, item.reason = "duplicate"',
        '            if False:\n                item.status, item.reason = "duplicate"',
        IMPORT_TESTS,
    ),
    Mutation(
        "I-8",
        "a source cannot switch between real and synthetic",
        IMPORT,
        "        if source.is_synthetic != manifest.source.synthetic:",
        "        if False:",
        IMPORT_TESTS,
    ),
    Mutation(
        "I-9",
        "commands preview before changing anything",
        CLI,
        "    if args.confirm is None:",
        "    if False:",
        IMPORT_TESTS,
    ),
    # --- the API: access, limits, audit --------------------------------------------------------
    Mutation(
        "A-1",
        "only staff reach the collection",
        "server/lexflow/main.py",
        "    app.include_router(judgments.router, prefix=API_PREFIX, dependencies=staff)",
        "    app.include_router(judgments.router, prefix=API_PREFIX, dependencies=[Depends(require_user)])",
        API_TESTS,
    ),
    Mutation(
        "A-2",
        "semantic search refuses (409) when it cannot run",
        API,
        '        if isinstance(provider, str):\n            raise ProblemError(409, "semantic-search-unavailable", provider)\n',
        "",
        API_TESTS,
    ),
    Mutation(
        "A-3",
        "searches are audited",
        API,
        '    audit.record(\n        "judgment.searched",',
        '    (lambda *a, **k: None)(\n        "judgment.searched",',
        API_TESTS,
    ),
    Mutation(
        "A-4",
        "queries are at most 300 characters",
        API,
        "max_length=service.QUERY_MAX",
        "max_length=100_000",
        API_TESTS,
    ),
    Mutation(
        "A-5",
        "search pages are bounded",
        API,
        "    page: int = Query(default=1, ge=1, le=SEARCH_PAGES),",
        "    page: int = Query(default=1, ge=1),",
        API_TESTS,
    ),
    # --- retrieval -------------------------------------------------------------------------------
    Mutation(
        "R-1",
        "vectors of another model are never compared",
        SERVICE,
        "                JudgmentChunkEmbedding.model == provider.model,\n                JudgmentChunkEmbedding.content_sha256 == JudgmentChunk.content_sha256,\n",
        "                JudgmentChunkEmbedding.content_sha256 == JudgmentChunk.content_sha256,\n",
        API_TESTS,
    ),
    Mutation(
        "R-2",
        "a vector of old text is never used",
        SERVICE,
        "                JudgmentChunkEmbedding.model == provider.model,\n                JudgmentChunkEmbedding.content_sha256 == JudgmentChunk.content_sha256,\n",
        "                JudgmentChunkEmbedding.model == provider.model,\n",
        API_TESTS,
    ),
    # --- the UI ------------------------------------------------------------------------------------
    Mutation(
        "U-1",
        "source links are https only",
        UI,
        "  if (!url.startsWith('https://')) return null;",
        "",
        UI_TESTS,
    ),
    Mutation(
        "U-2",
        "unavailable search modes cannot be chosen",
        UI,
        "disabled={!available(m)}",
        "disabled={false}",
        UI_TESTS,
    ),
    Mutation(
        "U-3",
        "results never outlive their query",
        "src/hooks/useJudgments.ts",
        "    queryKey: ['judgments', 'search', query],",
        "    queryKey: ['judgments', 'search'],",
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


def main() -> int:
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
        f"Phase 4 mutation checks at commit {head}, started {started:%Y-%m-%d %H:%M:%S} UTC",
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
        "# Phase 4 mutation checks",
        "",
        (
            f"Commit `{head}`; run {started:%Y-%m-%d %H:%M} UTC; script "
            "`docs/verification/phase4/run_mutation_checks.py` (raw output: "
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
