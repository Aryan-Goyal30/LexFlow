"""Embeddings mutation checks: break one guard at a time and confirm a test fails.

    server\\.venv\\Scripts\\python docs/verification/embeddings/run_mutation_checks.py

Each check replaces one exact snippet in one source file, runs the tests that
should notice, and restores the file byte-for-byte (verified) before the next.
A check passes ("caught") when the tests FAIL with the guard removed.

The tests use only the test database (``lexflow_test`` via ``TEST_DATABASE_URL``,
which must point at a PostgreSQL server with pgvector). Refuses to start if any
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


RETRIEVAL = "server/lexflow/services/retrieval.py"
INDEXING = "server/lexflow/services/indexing.py"
MODELS_CLI = "server/lexflow/cli/models.py"
SEARCH_API = "server/lexflow/api/search.py"
SEARCH_TESTS = pytest("tests/test_search.py")
INDEX_TESTS = pytest("tests/test_indexing.py")
EMB_TESTS = pytest("tests/test_embeddings.py")

MUTATIONS = [
    # --- search: what may be searched --------------------------------------------------
    Mutation(
        "S-1",
        "deleted documents are never searched",
        RETRIEVAL,
        "        Document.deleted_at.is_(None),\n",
        "",
        SEARCH_TESTS,
    ),
    Mutation(
        "S-2",
        "a search stays inside its case",
        RETRIEVAL,
        "        Document.case_id == case_id,\n",
        "",
        SEARCH_TESTS,
    ),
    Mutation(
        "S-3",
        "a vector of old text is never used",
        RETRIEVAL,
        "                DocumentChunkEmbedding.content_sha256 == DocumentChunk.content_sha256,\n",
        "",
        SEARCH_TESTS,
    ),
    Mutation(
        "S-4",
        "vectors of another model are never compared",
        RETRIEVAL,
        "                DocumentChunkEmbedding.model == provider.model,\n",
        "",
        SEARCH_TESTS,
    ),
    Mutation(
        "S-5",
        "semantic search refuses (409) when it cannot run",
        SEARCH_API,
        "        if isinstance(provider, str):\n            raise _unavailable(provider)\n",
        "",
        SEARCH_TESTS,
    ),
    Mutation(
        "S-6",
        "each search is audited",
        SEARCH_API,
        '    audit.record(\n        "case.searched",',
        '    (lambda *a, **k: None)(\n        "case.searched",',
        SEARCH_TESTS,
    ),
    # --- indexing --------------------------------------------------------------------------
    Mutation(
        "I-1",
        "current vectors are not embedded again",
        INDEXING,
        "    todo = [c for c in chunks if current.get(c.id) != c.content_sha256]",
        "    todo = list(chunks)",
        INDEX_TESTS,
    ),
    Mutation(
        "I-2",
        "finished batches are kept after a failure",
        INDEXING,
        "            session.commit()  # partial progress survives a crash\n",
        "",
        INDEX_TESTS,
    ),
    Mutation(
        "I-3",
        "a document locked by another worker is skipped",
        INDEXING,
        '            if not connection.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": key}):',
        "            if False:",
        INDEX_TESTS,
    ),
    Mutation(
        "I-4",
        "text extracted again during indexing discards the result",
        INDEXING,
        "            if _job_marker(session, document_id) != marker:",
        "            if False:",
        INDEX_TESTS,
    ),
    Mutation(
        "I-5",
        "without embeddings, extracted text is not queued for indexing",
        "server/lexflow/worker.py",
        'index_status="disabled" if provider is None else "pending"',
        'index_status="pending"',
        pytest("tests/test_worker.py"),
    ),
    # --- the model and its command line ----------------------------------------------------
    Mutation(
        "M-1",
        "missing or damaged model files are refused",
        "server/lexflow/embeddings.py",
        "        if problems:\n",
        "        if False:\n",
        EMB_TESTS,
    ),
    Mutation(
        "M-2",
        "a download that does not match its SHA-256 is refused",
        MODELS_CLI,
        "        if digest.hexdigest() != sha256:",
        "        if False:",
        EMB_TESTS,
    ),
    Mutation(
        "M-3",
        "download previews before fetching",
        MODELS_CLI,
        "    if not args.confirm:",
        "    if False:",
        EMB_TESTS,
    ),
    Mutation(
        "M-4",
        "queue-indexing leaves current vectors alone",
        MODELS_CLI,
        "                & (DocumentExtraction.embedding_model != MODEL_KEY),",
        "                & (DocumentExtraction.embedding_model != None),",
        EMB_TESTS,
    ),
    Mutation(
        "M-5",
        "queue-indexing previews before changing anything",
        MODELS_CLI,
        '    if args.confirm is None:\n        print(\n            f"Preview only: nothing was changed. To queue these {len(rows)} document(s) for "',
        '    if False:\n        print(\n            f"Preview only: nothing was changed. To queue these {len(rows)} document(s) for "',
        EMB_TESTS,
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
        f"Embeddings mutation checks at commit {head}, started {started:%Y-%m-%d %H:%M:%S} UTC",
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
        "# Embeddings mutation checks",
        "",
        (
            f"Commit `{head}`; run {started:%Y-%m-%d %H:%M} UTC; script "
            "`docs/verification/embeddings/run_mutation_checks.py` (raw output: "
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
