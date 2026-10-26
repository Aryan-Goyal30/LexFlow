"""Evaluate judgment search on the imported genuine corpus (Batch 2), read-only.

    .venv\\Scripts\\python scripts/evaluate_genuine_retrieval.py MANIFEST
        [--database lexflow_e2e] [--set FOLDER ...] [--out DIR]

Runs every query of each relevance set through the same search functions as
the API (keyword, semantic and hybrid; ``origin=genuine``) against the named
e2e database, in a READ ONLY transaction, and reports Recall@k, Precision@k,
MRR and nDCG@k with each set's own wording (``relevance_sets.describe``).

Sets:
- every ``--set`` folder (for example the model-generated known-item set);
- a **citation-context proxy** set built here from the corpus itself. Where
  one corpus judgment cites another, the text around the citation (at most
  300 characters, with the cited case's names and citations removed) is the
  query, and the cited judgment the target. The citing judgment is left out
  of its own ranking. Written under ``var/judgments/eval/`` (outside Git:
  it contains excerpts). A citation is a signal, not lawyer relevance.

The database guards are those of ``preview_judgment_import.py``. Nothing
leaves this computer: embeddings use the local model files only.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

SERVER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_ROOT))

from lexflow import relevance_sets as sets  # noqa: E402
from lexflow.config import Settings  # noqa: E402
from lexflow.demo import DEMO_MARKER  # noqa: E402
from lexflow.embeddings import EmbeddingProvider, provider_for  # noqa: E402
from lexflow.models import JudgmentSection  # noqa: E402
from lexflow.services import judgment_import as importer  # noqa: E402
from lexflow.services import judgments as service  # noqa: E402

KS = (1, 3, 5, 10)
MODES: tuple[service.Mode, ...] = ("keyword", "semantic", "hybrid")
WINDOW = 300
# How each corpus judgment is cited by name (pattern), and the strings removed
# from a citing context so the query does not name its own answer.
CITED = {
    "sha256-ab93f027284b90a8": (
        r"Amritdhara",
        [r"Amritdhara[^,.;]*", r"Satyadeo Gupta", r"AIR 1963 SC 449"],
    ),
    "sha256-843dab1e08d0d71a": (
        r"Parle Products",
        [r"Parle Products[^,.;]*", r"J\.\s?P\.\s?& Co\.?,?( Mysore)?"],
    ),
    "sha256-624744063b0e2ff8": (
        r"Nandhini Deluxe",
        [
            r"Nandhini Deluxe",
            r"Karnataka Co-?operative Milk Producers Federation( Limited| Ltd\.?)?",
        ],
    ),
    "sha256-dbcbb6d4167b11c6": (
        r"Renaissance Hotel Holdings",
        [r"Renaissance Hotel Holdings Inc\.?", r"B\. Vijaya Sai( and Others)?"],
    ),
}


def guard_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "lexflow_preview_guard", SERVER_ROOT / "scripts" / "preview_judgment_import.py"
    )
    if spec is None or spec.loader is None:
        raise SystemExit("Cannot load the database guard.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def citation_proxy(
    session: Session, manifest: dict[str, Any], keys: dict[Any, str], out: Path
) -> tuple[sets.RelevanceSet, dict[str, str]]:
    """Build the citation-context set; returns it and query id -> citing key."""
    source = manifest["source"]["key"]
    texts: dict[str, str] = {}
    for entry in manifest["judgments"]:
        jid = importer.judgment_id(source, entry["id"])
        sections = session.scalars(
            select(JudgmentSection.text)
            .where(JudgmentSection.judgment_id == jid)
            .order_by(JudgmentSection.number)
        )
        texts[entry["id"]] = re.sub(r"\s+", " ", " ".join(sections))
    queries: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    citing_of: dict[str, str] = {}
    for cited, (pattern, scrub) in CITED.items():
        for citing, body in texts.items():
            if citing == cited:
                continue
            for n, match in enumerate(list(re.finditer(pattern, body))[:3], start=1):
                start = max(0, match.start() - WINDOW // 2)
                window = body[start : start + WINDOW * 2]
                for item in scrub:
                    window = re.sub(item, " ", window, flags=re.I)
                window = re.sub(
                    r"\b\d{4}\s*\(\d+\)\s*SCC\s*\d+|\bAIR\s+\d{4}\s+SC\s+\d+", " ", window
                )
                query = re.sub(r"\s+", " ", window).strip()[:WINDOW]
                qid = f"cite-{citing[:14]}-{cited[:14]}-{n}"
                queries.append({"query_id": qid, "area": "Trade marks", "summary": query})
                labels.append(
                    {
                        "query_id": qid,
                        "judgment": {"source_key": source, "id": cited},
                        "grade": sets.RELEVANT,
                        "reason": "cited at this point by another corpus judgment (proxy)",
                        "reviewer": sets.PROXY_REVIEWER,
                        "labelled_on": datetime.now(UTC).date().isoformat(),
                    }
                )
                citing_of[qid] = f"{source}:{citing}"
    out.mkdir(parents=True, exist_ok=True)
    info = {
        "name": "sci-tm-citation-context",
        "version": 1,
        "label_origin": "citation-proxy",
        "guide_version": "citation-context proxy",
        "corpus": {
            "source_key": source,
            "manifest_sha256": hashlib.sha256(json.dumps(manifest).encode()).hexdigest(),
        },
    }
    (out / "set.json").write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8")
    (out / "queries.jsonl").write_text(
        "".join(json.dumps(q, ensure_ascii=False) + "\n" for q in queries), encoding="utf-8"
    )
    (out / "labels.jsonl").write_text(
        "".join(json.dumps(lab) + "\n" for lab in labels), encoding="utf-8"
    )
    return sets.load(out), citing_of


def run_set(
    session: Session,
    relevance: sets.RelevanceSet,
    keys: dict[Any, str],
    provider: EmbeddingProvider,
    exclude: dict[str, str],
) -> dict[str, Any]:
    result: dict[str, Any] = {"label": relevance.describe(), "modes": {}}
    filters = service.Filters(origin="genuine")
    for mode in MODES:
        rankings: dict[str, list[str]] = {}
        empty = 0
        for qid, query in relevance.queries.items():
            ranked = service.search(session, mode, query.summary, filters, provider)
            keys_ranked = [keys[r.judgment_id] for r in ranked if r.judgment_id in keys]
            keys_ranked = [k for k in keys_ranked if k != exclude.get(qid)]
            empty += not keys_ranked
            rankings[qid] = keys_ranked
        reports = {k: sets.evaluate(relevance, rankings, k) for k in KS}
        result["modes"][mode] = {
            "queries_with_no_results": empty,
            "by_k": {
                k: {f: v for f, v in asdict(r).items() if f not in ("per_query", "label")}
                for k, r in reports.items()
            },
            "first_relevant_rank": {
                q.query_id: (round(1 / q.reciprocal_rank) if q.reciprocal_rank else None)
                for q in reports[10].per_query
            },
        }
    return result


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


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Retrieval evaluation on the genuine corpus (generated)",
        "",
        f"- Run: {report['run_at']}; commit `{report['commit']}` (plus uncommitted changes)",
        f"- Database: `{report['database']}` (read-only); filter `origin=genuine`",
        f"- Corpus manifest SHA-256 `{report['manifest_sha256']}`; {report['judgments']} judgments",
        f"- Embedding model: `{report['model']}` (local files)",
        "",
    ]
    for name, result in report["sets"].items():
        lines += [f"## {name}", "", f"**{result['label']}**", ""]
        lines += [
            "| Mode | k | Queries scored | Recall@k | Precision@k | MRR | nDCG@k | "
            "Unjudged in top k | Queries with no results |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for mode, data in result["modes"].items():
            for k, row in data["by_k"].items():
                lines.append(
                    f"| {mode} | {k} | {row['queries']} | {row['recall']:.3f} | "
                    f"{row['precision']:.3f} | {row['mrr']:.3f} | {row['ndcg']:.3f} | "
                    f"{row['unjudged']} | {data['queries_with_no_results']} |"
                )
        lines.append("")
        skipped = next(iter(result["modes"].values()))["by_k"][KS[-1]]["skipped"]
        if skipped:
            lines += ["Skipped: " + "; ".join(skipped), ""]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--database", default="lexflow_e2e")
    parser.add_argument("--set", type=Path, action="append", default=[])
    parser.add_argument(
        "--out", type=Path, default=SERVER_ROOT.parent / "docs/verification/batch2/evaluation"
    )
    parser.add_argument(
        "--proxy-dir", type=Path, default=SERVER_ROOT / "var/judgments/eval/citation-context-v1"
    )
    args = parser.parse_args(argv)
    raw = args.manifest.read_bytes()
    manifest = json.loads(raw)
    manifest_sha = hashlib.sha256(raw).hexdigest()
    settings = Settings()
    provider = provider_for(settings.model_copy(update={"embeddings": "local"}))
    if provider is None:
        raise SystemExit("The local embedding model is needed for semantic and hybrid search.")
    url = guard_module().target_url(args.database, settings.database_url)
    engine = create_engine(url)
    source = manifest["source"]["key"]
    keys = {
        importer.judgment_id(source, e["id"]): f"{source}:{e['id']}" for e in manifest["judgments"]
    }
    report: dict[str, Any] = {
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": git_commit(),
        "database": args.database,
        "manifest_sha256": manifest_sha,
        "judgments": len(keys),
        "model": provider.model,
        "sets": {},
    }
    try:
        with Session(engine) as session:
            connected, marker = session.execute(
                text(
                    "SELECT current_database(), shobj_description(oid, 'pg_database') "
                    "FROM pg_database WHERE datname = current_database()"
                )
            ).one()
            if connected != args.database or marker != DEMO_MARKER:
                raise SystemExit("Refusing: not the marked isolated database.")
            session.execute(text("SET TRANSACTION READ ONLY"))
            for folder in args.set:
                relevance = sets.load(folder)
                corpus = relevance.info.corpus
                if corpus is not None and corpus.manifest_sha256 != manifest_sha:
                    raise SystemExit(f"{folder}: the set was written for another manifest.")
                report["sets"][relevance.info.name] = run_set(
                    session, relevance, keys, provider, {}
                )
            proxy, citing = citation_proxy(session, manifest, keys, args.proxy_dir)
            report["sets"][proxy.info.name] = run_set(session, proxy, keys, provider, citing)
            report["sets"][proxy.info.name]["queries"] = len(proxy.queries)
            session.rollback()
    finally:
        engine.dispose()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "genuine-retrieval.json").write_text(
        json.dumps(report, indent=1, default=str) + "\n", encoding="utf-8"
    )
    (args.out / "genuine-retrieval.md").write_text(markdown(report), encoding="utf-8")
    print(markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
