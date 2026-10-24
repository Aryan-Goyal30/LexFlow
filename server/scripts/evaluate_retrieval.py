"""Measure case search (keyword, semantic, hybrid) on the FICTIONAL test corpus.

    .venv\\Scripts\\python scripts/evaluate_retrieval.py [--out DIR]

Builds a throwaway database ``lexflow_eval_test`` on the test server (from
``TEST_DATABASE_URL``; the name must contain "test"), loads the fictional
documents in ``tests/fixtures/retrieval/fictional_corpus.json`` through the
real extraction-queue and indexing code, embeds them with the real local model
(it must be downloaded first: ``python -m lexflow.cli.models download``), and
runs every query in every mode through the same functions the API uses.

For each query exactly one page answers it, so Recall@k is the share of
queries whose answer is in the top k. MRR is the mean of 1/rank of the answer
(0 when it is not in the top 10). Results are written as JSON and Markdown;
the database is dropped at the end. Nothing leaves this computer.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import URL, create_engine, make_url, text
from sqlalchemy.orm import Session

SERVER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_ROOT))

from lexflow.config import get_settings  # noqa: E402
from lexflow.embeddings import LocalBgeProvider, model_path  # noqa: E402
from lexflow.extraction import Section  # noqa: E402
from lexflow.extraction.chunking import chunk_sections  # noqa: E402
from lexflow.models import Document  # noqa: E402
from lexflow.services import extraction_queue as queue  # noqa: E402
from lexflow.services import indexing, retrieval  # noqa: E402

CORPUS = SERVER_ROOT / "tests" / "fixtures" / "retrieval" / "fictional_corpus.json"
DATABASE = "lexflow_eval_test"
KS = (1, 3, 5)
DEPTH = 10
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
    url = url.set(database=DATABASE)
    if "test" not in (url.database or ""):  # pragma: no cover - constant name
        raise SystemExit("refusing: the evaluation database name must contain 'test'")
    return url


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


def load(session: Session, corpus: dict) -> tuple[uuid.UUID, dict[uuid.UUID, str]]:  # type: ignore[type-arg]
    """The fictional sample data, then the corpus as documents of the sample Sattvik case."""
    from lexflow.seed import sample_uuid
    from lexflow.seed.loader import load_sample_data

    load_sample_data(session)
    session.commit()
    case_id = sample_uuid("case", "case-1005")
    names: dict[uuid.UUID, str] = {}
    for item in corpus["documents"]:
        document = Document(
            case_id=case_id,
            name=item["name"],
            document_type="PDF",
            content_type="application/pdf",
            size_bytes=1,
            sha256="0" * 64,
            storage_key=uuid.uuid4().hex,
            uploaded_on=NOW.date(),
        )
        session.add(document)
        session.flush()
        queue.queue(session, document, requested_by=None, now=NOW)
        session.commit()
        if (
            queue.claim(session, worker_id="eval", now=NOW, lease_seconds=300, max_attempts=3)
            != document.id
        ):
            raise SystemExit("the evaluation database had another job waiting")
        sections = [Section(n, page) for n, page in enumerate(item["pages"], start=1)]
        queue.complete(
            session,
            document.id,
            worker_id="eval",
            outcome=queue.Success(
                sections=sections,
                chunks=chunk_sections(sections, 1200, 200),
                extractor="fixture",
                page_count=len(sections),
            ),
            now=NOW,
            max_attempts=3,
            index_status="pending",
        )
        names[document.id] = item["name"]
    return case_id, names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out", type=Path, default=SERVER_ROOT.parent / "docs" / "verification" / "embeddings"
    )
    args = parser.parse_args()
    url = eval_url()  # first: refuse a URL that would connect elsewhere
    settings = get_settings()
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    provider = LocalBgeProvider(
        model_path(settings), threads=settings.embedding_threads, batch_size=8
    )
    recreate(url)
    try:
        migrate(url)
        engine = create_engine(url)
        with Session(engine) as session:
            case_id, names = load(session, corpus)
        started = time.monotonic()
        with Session(engine) as session:
            for document_id in names:
                result = indexing.index_document(
                    session, provider, document_id, batch_size=8, now=lambda: NOW
                )
                if result.status != "indexed":
                    raise SystemExit(f"indexing failed: {result}")
        index_seconds = time.monotonic() - started

        rows = []
        with Session(engine) as session:
            for q in corpus["queries"]:
                wanted = {(name, page) for name, page in q["relevant"]}
                ranks = {}
                for mode in ("keyword", "semantic", "hybrid"):
                    if mode == "keyword":
                        hits = retrieval.keyword(session, case_id, q["query"], DEPTH)
                    elif mode == "semantic":
                        hits = retrieval.semantic(session, provider, case_id, q["query"], DEPTH)
                    else:
                        hits = retrieval.hybrid(session, provider, case_id, q["query"], DEPTH)
                    found = [
                        rank
                        for rank, hit in enumerate(hits, start=1)
                        if (names[hit.document_id], hit.page_number) in wanted
                    ]
                    ranks[mode] = found[0] if found else None
                rows.append({"query": q["query"], "kind": q["kind"], "ranks": ranks})
        engine.dispose()
    finally:
        recreate(url, drop_only=True)

    def metrics(subset: list[dict], mode: str) -> dict[str, float]:  # type: ignore[type-arg]
        ranks = [r["ranks"][mode] for r in subset]
        out = {f"recall@{k}": sum(1 for x in ranks if x and x <= k) / len(ranks) for k in KS}
        out["mrr@10"] = sum(1 / x for x in ranks if x) / len(ranks)
        return {k: round(v, 3) for k, v in out.items()}

    kinds = {"all": rows} | {
        kind: [r for r in rows if r["kind"] == kind] for kind in ("lexical", "paraphrase")
    }
    summary = {
        kind: {mode: metrics(subset, mode) for mode in ("keyword", "semantic", "hybrid")}
        for kind, subset in kinds.items()
    }
    pages = sum(len(d["pages"]) for d in corpus["documents"])
    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": provider.model,
        "corpus": "tests/fixtures/retrieval/fictional_corpus.json (FICTIONAL)",
        "documents": len(corpus["documents"]),
        "pages": pages,
        "queries": {kind: len(subset) for kind, subset in kinds.items()},
        "index_seconds": round(index_seconds, 2),
        "metrics": summary,
        "per_query": rows,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "retrieval-eval.json").write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    lines = [
        "# Case search evaluation (FICTIONAL corpus)",
        "",
        f"Model `{provider.model}`; {len(corpus['documents'])} documents, {pages} pages; "
        f"{len(rows)} queries ({len(kinds['lexical'])} lexical, "
        f"{len(kinds['paraphrase'])} paraphrase); indexing took "
        f"{index_seconds:.2f} s on the CPU. Generated by "
        "`server/scripts/evaluate_retrieval.py`.",
        "",
        "Each query has exactly one answering page, so Recall@k is the share of queries "
        "whose answer is in the top k; MRR@10 is the mean reciprocal rank (0 if not in the "
        "top 10). The corpus and queries were written by the developer: this checks "
        "plumbing and gross behaviour, not legal research quality.",
        "",
    ]
    for kind in ("all", "lexical", "paraphrase"):
        lines += [
            f"## {kind.capitalize()} queries ({len(kinds[kind])})",
            "",
            "| Mode | Recall@1 | Recall@3 | Recall@5 | MRR@10 |",
            "|---|---|---|---|---|",
        ]
        for mode, m in summary[kind].items():
            lines.append(
                f"| {mode} | {m['recall@1']} | {m['recall@3']} | {m['recall@5']} | {m['mrr@10']} |"
            )
        lines.append("")
    lines += [
        "## Per query (rank of the answering page; - = not in the top 10)",
        "",
        "| Kind | Query | keyword | semantic | hybrid |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        cells = [str(r["ranks"][m] or "-") for m in ("keyword", "semantic", "hybrid")]
        lines.append(f"| {r['kind']} | {r['query']} | " + " | ".join(cells) + " |")
    (args.out / "retrieval-eval.md").write_text("\n".join(lines) + "\n", "utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
