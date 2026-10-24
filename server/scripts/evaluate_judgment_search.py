"""Evaluate judgment search on a versioned evaluation set (Phase 4).

    .venv\\Scripts\\python scripts/evaluate_judgment_search.py
        [--set tests/fixtures/judgments/evaluation/synthetic-eval-v1.json]
        [--out ../docs/verification/phase4]

Builds a throwaway database ``lexflow_eval_test`` on the test server (from
``TEST_DATABASE_URL``; the name must contain "test"), imports the set's corpus
through the real importer (checking the manifest's SHA-256 against the one
the set records), embeds it with the local model when its files are present,
runs every query in every available mode through the same search functions
the API uses, and writes ``judgment-eval.json`` and ``judgment-eval.md``.
Modes that cannot run are reported as skipped, with the reason. The database
is dropped at the end. Nothing leaves this computer.

The shipped set is SYNTHETIC: invented judgments and developer-written
labels. Its numbers check the machinery; they say nothing about legal
research quality, which needs a licensed corpus and a lawyer's labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from sqlalchemy import URL, create_engine, make_url, select, text
from sqlalchemy.orm import Session

SERVER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_ROOT))

from lexflow.config import get_settings  # noqa: E402
from lexflow.embeddings import (  # noqa: E402  # noqa: E402
    EmbeddingProvider,
    EmbeddingsUnavailableError,
    LocalBgeProvider,
    model_path,
)
from lexflow.evaluation import QueryResult, by_kind, summarise  # noqa: E402
from lexflow.extraction import Extracted, Limits, extract  # noqa: E402
from lexflow.models import Judgment  # noqa: E402
from lexflow.services import judgment_import as importer  # noqa: E402
from lexflow.services import judgments as service  # noqa: E402

DATABASE = "lexflow_eval_test"
DEFAULT_SET = (
    SERVER_ROOT / "tests" / "fixtures" / "judgments" / "evaluation" / "synthetic-eval-v1.json"
)
EXTRA_KS = (1, 3, 5)
NOW = datetime(2026, 6, 1, tzinfo=UTC)


def eval_url() -> URL:
    raw = os.environ.get("TEST_DATABASE_URL") or dotenv_values(SERVER_ROOT / ".env").get(
        "TEST_DATABASE_URL"
    )
    if not raw:
        raise SystemExit("TEST_DATABASE_URL is not set (see server/.env.example)")
    url = make_url(raw)
    if {"dbname", "service"} & set(url.query):
        # Either would make psycopg connect to another database than the throwaway
        # one named below, and the evaluation would migrate it and write test data there.
        raise SystemExit("Refusing a TEST_DATABASE_URL with a dbname or service parameter.")
    return url.set(database=DATABASE)


def recreate(url: URL, *, drop_only: bool = False) -> None:
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{DATABASE}" WITH (FORCE)'))
        if not drop_only:
            connection.execute(text(f'CREATE DATABASE "{DATABASE}"'))
    admin.dispose()


def migrate(url: URL) -> None:
    from alembic import command
    from alembic.config import Config

    config = Config(str(SERVER_ROOT / "alembic.ini"))
    config.attributes["database_url"] = url.render_as_string(hide_password=False)
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")


def in_process(content_type: str, data: bytes, limits: Limits, timeout: float) -> Extracted:
    return extract(content_type, data, limits)


def git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607 - git from PATH
            cwd=SERVER_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def load_set(path: Path) -> tuple[dict[str, Any], Path, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != "lexflow-judgment-eval/1":
        raise SystemExit(f"{path.name}: not a lexflow-judgment-eval/1 file")
    ids = [q["id"] for q in data["queries"]]
    if len(ids) != len(set(ids)):
        raise SystemExit(f"{path.name}: query ids are not unique")
    manifest = (path.parent / data["corpus"]["manifest"]).resolve()
    actual = hashlib.sha256(manifest.read_bytes()).hexdigest()
    if actual != data["corpus"]["manifest_sha256"]:
        raise SystemExit(
            f"The corpus changed: {manifest.name} has SHA-256 {actual}, the set records "
            f"{data['corpus']['manifest_sha256']}. Update the set's version and hash."
        )
    return data, manifest, hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--set", type=Path, default=DEFAULT_SET)
    parser.add_argument(
        "--out", type=Path, default=SERVER_ROOT.parent / "docs" / "verification" / "phase4"
    )
    args = parser.parse_args()
    url = eval_url()  # first: refuse a URL that would connect elsewhere
    evalset, manifest, set_sha = load_set(args.set)
    k = int(evalset["k"])
    settings = get_settings()

    provider: EmbeddingProvider | None = None
    skipped: dict[str, str] = {}
    try:
        provider = LocalBgeProvider(
            model_path(settings), threads=settings.embedding_threads, batch_size=16
        )
    except EmbeddingsUnavailableError as exc:
        skipped = {"semantic": str(exc), "hybrid": str(exc)}
    modes: list[service.Mode] = ["keyword"]
    if provider is not None:
        modes += ["semantic", "hybrid"]

    recreate(url)
    rows: list[dict[str, Any]] = []
    try:
        migrate(url)
        engine = create_engine(url)
        with Session(engine) as session:
            plan = importer.plan_import(session, manifest, max_bytes=10_000_000)
            outcome = importer.apply_import(
                session,
                plan,
                update=False,
                limits=Limits(
                    max_pages=1000, max_text_bytes=5_000_000, max_unpacked_bytes=200_000_000
                ),
                timeout_seconds=60,
                extract=in_process,
                operator="evaluation",
                now=NOW,
            )
            if outcome.rejected:
                raise SystemExit(f"The corpus did not import cleanly: {outcome.rejected}")
            keys: dict[uuid.UUID, str] = {
                jid: key
                for jid, key in session.execute(select(Judgment.id, Judgment.source_document_id))
            }
            if provider is not None:
                for judgment_id in keys:
                    service.index_judgment(
                        session, provider, judgment_id, batch_size=16, now=lambda: NOW
                    )
            results: dict[str, list[QueryResult]] = {mode: [] for mode in modes}
            for q in evalset["queries"]:
                row: dict[str, Any] = {
                    "id": q["id"],
                    "kind": q["kind"],
                    "query": q["query"],
                    "relevant": q["relevant"],
                    "ranks": {},
                    "top3": {},
                }
                for mode in modes:
                    ranked = service.search(session, mode, q["query"], service.Filters(), provider)
                    keyed = tuple(keys[hit.judgment_id] for hit in ranked)
                    results[mode].append(
                        QueryResult(q["id"], q["kind"], frozenset(q["relevant"]), keyed)
                    )
                    first = next(
                        (i for i, key in enumerate(keyed[:k], 1) if key in q["relevant"]), None
                    )
                    row["ranks"][mode] = first
                    row["top3"][mode] = list(keyed[:3])
                rows.append(row)
        engine.dispose()
    finally:
        recreate(url, drop_only=True)

    corpus_keys = set(keys.values())
    metrics: dict[str, dict[str, Any]] = {}
    for mode in modes:
        metrics[mode] = {}
        for kind, group in by_kind(results[mode]).items():
            main_summary = summarise(group, k, corpus_keys)
            entry = {
                f"recall@{k}": main_summary.recall,
                f"precision@{k}": main_summary.precision,
                f"mrr@{k}": main_summary.mrr,
                "queries": main_summary.queries,
                "no_answer_queries": main_summary.no_answer_queries,
                "no_answer_with_no_results": main_summary.no_answer_empty,
                "errors": main_summary.errors,
            }
            for extra in EXTRA_KS:
                entry[f"recall@{extra}"] = summarise(group, extra, corpus_keys).recall
            metrics[mode][kind] = entry

    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_commit": git_commit(),
        "synthetic": True,
        "evaluation_set": {"version": evalset["version"], "sha256": set_sha, "queries": len(rows)},
        "corpus": {
            "manifest_sha256": evalset["corpus"]["manifest_sha256"],
            "judgments": len(corpus_keys),
        },
        "model": provider.model if provider else None,
        "modes_run": modes,
        "modes_skipped": skipped,
        "k": k,
        "metrics": metrics,
        "per_query": rows,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "judgment-eval.json").write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    lines = [
        "# Judgment search evaluation (SYNTHETIC engineering check)",
        "",
        f"Set `{evalset['version']}` ({len(rows)} queries), corpus of {len(corpus_keys)} "
        f"synthetic judgments (manifest SHA-256 `{evalset['corpus']['manifest_sha256'][:16]}…`), "
        f"commit `{report['git_commit']}`, model `{report['model']}`, K = {k}. Generated by "
        "`server/scripts/evaluate_judgment_search.py`.",
        "",
        "**What this is not:** the judgments are invented and the relevance labels were "
        "written by the developer. These numbers test the search machinery; legal research "
        "quality is **unevaluated** until a licensed corpus and a lawyer's relevance labels exist.",
        "",
    ]
    if skipped:
        lines += [f"Skipped modes: {', '.join(f'{m} ({r})' for m, r in skipped.items())}", ""]
    for kind in ("all", "lexical", "paraphrase", "no-answer"):
        lines += [
            f"## {kind}",
            "",
            f"| Mode | Recall@1 | Recall@3 | Recall@5 | Recall@{k} | Precision@{k} | MRR@{k} "
            "| Queries | No-answer queries with no results |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for mode in modes:
            m = metrics[mode].get(kind)
            if m is None:
                continue
            lines.append(
                f"| {mode} | {m['recall@1']} | {m['recall@3']} | {m['recall@5']} "
                f"| {m[f'recall@{k}']} "
                f"| {m[f'precision@{k}']} | {m[f'mrr@{k}']} | {m['queries']} "
                f"| {m['no_answer_with_no_results']}/{m['no_answer_queries']} |"
            )
        lines.append("")
    lines += [
        f"Precision@{k} divides by {k}: with one or two relevant judgments per query its ceiling "
        f"is 0.1–0.2, so it is mainly useful for comparing modes.",
        "",
        "## Per query (rank of the first relevant judgment in the top K; - = none)",
        "",
        "| Id | Kind | Query | " + " | ".join(modes) + " |",
        "|---|---|---|" + "---|" * len(modes),
    ]
    for row in rows:
        cells = [str(row["ranks"][m] or "-") for m in modes]
        lines.append(
            f"| {row['id']} | {row['kind']} | {row['query']} | " + " | ".join(cells) + " |"
        )
    (args.out / "judgment-eval.md").write_text("\n".join(lines) + "\n", "utf-8")
    print(json.dumps({m: metrics[m]["all"] for m in modes}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
