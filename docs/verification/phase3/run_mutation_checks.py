"""Phase 3 mutation checks: break one guard at a time and confirm a test fails.

    server\\.venv\\Scripts\\python docs/verification/phase3/run_mutation_checks.py

Each check replaces one exact snippet in one source file, runs the tests that
should notice, and restores the file byte-for-byte (verified) before the next.
A check passes ("caught") when the tests FAIL with the guard removed.

The tests use only the test databases (``lexflow_test``, via server/.env
``TEST_DATABASE_URL``) and the fake API in the front-end tests. Refuses to start
if any target file has uncommitted changes. Writes, next to this script:
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


DOC_TEXT = "server/lexflow/services/document_text.py"
DOC_API = "server/lexflow/api/documents.py"
DOC_TAB = "src/components/workspace/DocumentsTab.tsx"
CLI_DOCS = "server/lexflow/cli/documents.py"
TEXT_TESTS = pytest("tests/test_document_text.py")
CLI_TESTS = pytest("tests/test_cli_documents.py")
EMB_TESTS = pytest("tests/test_embeddings.py")

MUTATIONS = [
    # --- P3-M4: text viewer, retry, audit -------------------------------------------
    Mutation(
        "M4-1",
        "text is served only once it is ready",
        DOC_TEXT,
        '    if job is None or job.status != "ready":\n        raise not_available(document, job)',
        "    if job is None:\n        raise not_available(document, job)",
        TEXT_TESTS,
    ),
    Mutation(
        "M4-2",
        "a retry needs permission to add documents",
        DOC_API,
        "        Action.UPLOAD_DOCUMENT,\n        audit,\n        lock=True,\n    )\n    previous =",
        "        Action.VIEW,\n        audit,\n        lock=True,\n    )\n    previous =",
        pytest(
            "tests/test_document_text.py",
            "tests/test_access_required.py",
            "tests/test_portal.py",
        ),
    ),
    Mutation(
        "M4-3",
        "reading text is audited",
        DOC_API,
        '    audit.record(\n        "document.text_viewed",',
        '    (lambda *a, **k: None)(\n        "document.text_viewed",',
        TEXT_TESTS,
    ),
    Mutation(
        "M4-4",
        "no retry while already queued or processing",
        DOC_TEXT,
        '    if job.status in ("queued", "processing"):\n        raise ProblemError(\n'
        '            409, "already-processing"',
        '    if job.status in ():\n        raise ProblemError(\n            409, "already-processing"',
        TEXT_TESTS,
    ),
    Mutation(
        "M4-5",
        "Try again offered only to those who may upload",
        DOC_TAB,
        "{doc.processing?.status === 'failed' && canUploadDocuments && (",
        "{doc.processing?.status === 'failed' && (",
        vitest("src/pages/documentText.test.tsx"),
    ),
    Mutation(
        "M4-6",
        "View text offered only when the text is ready",
        DOC_TAB,
        "{doc.processing?.status === 'ready' && (",
        "{doc.processing?.status !== 'queued' && (",
        vitest(
            "src/pages/documentText.test.tsx", "src/pages/documentProcessing.test.tsx"
        ),
    ),
    # --- P3-M5: embeddings gate ---------------------------------------------------------
    Mutation(
        "M5-1",
        "local embeddings are refused",
        "server/lexflow/embeddings.py",
        '    if settings.embeddings == "disabled":\n        return None\n    raise',
        "    if True:\n        return None\n    raise",
        EMB_TESTS,
    ),
    Mutation(
        "M5-2",
        "the worker checks embeddings before claiming a job",
        "server/lexflow/worker.py",
        "    provider_for(settings)  # chunks are stored",
        "    pass  # chunks are stored",
        EMB_TESTS,
    ),
    # --- P3-M6: backfill and never-queued files ---------------------------------------
    Mutation(
        "M6-1",
        "backfill leaves existing jobs alone",
        CLI_DOCS,
        "        .where(Document.storage_key.is_not(None), "
        "DocumentExtraction.document_id.is_(None))",
        "        .where(Document.storage_key.is_not(None))",
        CLI_TESTS,
    ),
    Mutation(
        "M6-2",
        "backfill skips records without a stored file",
        CLI_DOCS,
        "        .where(Document.storage_key.is_not(None), "
        "DocumentExtraction.document_id.is_(None))",
        "        .where(DocumentExtraction.document_id.is_(None))",
        CLI_TESTS,
    ),
    Mutation(
        "M6-3",
        "backfill previews before changing anything",
        CLI_DOCS,
        '    if args.confirm is None:\n        print(\n            f"Preview only: nothing was '
        "changed. To queue",
        '    if False:\n        print(\n            f"Preview only: nothing was changed. To queue',
        CLI_TESTS,
    ),
    Mutation(
        "M6-4",
        "no retry for records without a stored file",
        DOC_TEXT,
        '    if document.storage_key is None:\n        raise ProblemError(422, "no-file", NO_FILE)',
        '    if False:\n        raise ProblemError(422, "no-file", NO_FILE)',
        TEXT_TESTS,
    ),
    Mutation(
        "M6-5",
        "never-queued files are explained honestly",
        DOC_TEXT,
        "        message = NO_FILE if document.storage_key is None else NEVER_QUEUED",
        "        message = NO_FILE",
        TEXT_TESTS,
    ),
    Mutation(
        "M6-6",
        "Extract text offered only for stored files",
        DOC_TAB,
        "{doc.hasFile && doc.processing === null && canUploadDocuments && (",
        "{doc.processing === null && canUploadDocuments && (",
        vitest("src/pages/documentText.test.tsx"),
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
        f"Phase 3 mutation checks at commit {head}, started {started:%Y-%m-%d %H:%M:%S} UTC",
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
        "# Phase 3 mutation checks",
        "",
        (
            f"Commit `{head}`; run {started:%Y-%m-%d %H:%M} UTC; script "
            "`docs/verification/phase3/run_mutation_checks.py` (raw output: "
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
