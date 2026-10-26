"""Verify an imported manifest against the isolated database, read-only.

    .venv\\Scripts\\python scripts/verify_judgment_import.py MANIFEST [--database lexflow_e2e]

For every manifest entry: the judgment row exists under the manifest's
source with the same title, court, date, citations and source URL; its
content hash equals the file's SHA-256; it has sections and chunks; and its
provenance row holds the neutral citation, the attribution and every
provenance field of the manifest plus the file hash. Also checks the latest
import run for this manifest. The same database guards as the preview apply.
Exit status 1 on any mismatch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from types import ModuleType

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

SERVER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_ROOT))

from lexflow.config import Settings  # noqa: E402
from lexflow.models import (  # noqa: E402
    Judgment,
    JudgmentChunk,
    JudgmentImportRun,
    JudgmentProvenance,
    JudgmentSection,
    JudgmentSource,
)
from lexflow.services import judgment_import as importer  # noqa: E402


def load_preview_guard() -> ModuleType:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "lexflow_preview_guard", SERVER_ROOT / "scripts" / "preview_judgment_import.py"
    )
    if spec is None or spec.loader is None:
        raise SystemExit("Cannot load the preview script's database guard.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify(session: Session, manifest_path: Path) -> list[str]:
    session.execute(text("SET TRANSACTION READ ONLY"))
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    folder = manifest_path.parent
    key = manifest["source"]["key"]
    problems: list[str] = []
    source = session.scalar(select(JudgmentSource).where(JudgmentSource.key == key))
    if source is None:
        return [f"source {key!r} is missing"]
    if source.is_synthetic != bool(manifest["source"].get("synthetic")):
        problems.append("source synthetic flag differs")
    stored = session.scalar(
        select(func.count()).select_from(Judgment).where(Judgment.source_id == source.id)
    )
    if stored != len(manifest["judgments"]):
        problems.append(
            f"{stored} judgments stored under {key}, manifest has {len(manifest['judgments'])}"
        )
    for entry in manifest["judgments"]:
        jid = importer.judgment_id(key, entry["id"])
        where = entry["id"]
        judgment = session.get(Judgment, jid)
        if judgment is None:
            problems.append(f"{where}: missing")
            continue
        sha = hashlib.sha256((folder / entry["file"]).read_bytes()).hexdigest()
        checks = {
            "title": (judgment.title, entry["title"]),
            "court": (judgment.court, entry["court"]),
            "source_url": (judgment.source_url, entry["source_url"]),
            "citation": (judgment.citation, entry.get("citation")),
            "decision_date": (
                judgment.decision_date.isoformat() if judgment.decision_date else None,
                entry.get("decision_date"),
            ),
            "content_sha256": (judgment.content_sha256, sha),
        }
        problems += [f"{where}: {k} {a!r} != {b!r}" for k, (a, b) in checks.items() if a != b]
        sections = session.scalar(
            select(func.count())
            .select_from(JudgmentSection)
            .where(JudgmentSection.judgment_id == jid)
        )
        chunks = session.scalar(
            select(func.count()).select_from(JudgmentChunk).where(JudgmentChunk.judgment_id == jid)
        )
        if not sections or sections != judgment.section_count or not chunks:
            problems.append(
                f"{where}: sections {sections}/{judgment.section_count}, chunks {chunks}"
            )
        record = session.get(JudgmentProvenance, jid)
        if record is None:
            problems.append(f"{where}: no provenance")
            continue
        expected = {**entry.get("provenance", {}), "file_sha256": sha}
        if record.source_record != expected:
            problems.append(f"{where}: provenance differs from the manifest")
        if record.neutral_citation != entry.get("neutral_citation"):
            problems.append(f"{where}: neutral citation differs")
        if record.attribution != manifest["source"].get("attribution"):
            problems.append(f"{where}: attribution differs")
    manifest_sha = hashlib.sha256(raw).hexdigest()
    run = session.scalar(
        select(JudgmentImportRun)
        .where(JudgmentImportRun.manifest_sha256 == manifest_sha)
        .order_by(JudgmentImportRun.started_at.desc())
    )
    if run is None:
        problems.append("no import run recorded for this manifest")
    elif run.counts.get("imported") != len(manifest["judgments"]) or run.counts.get("rejected"):
        problems.append(f"import run counts {run.counts}")
    session.rollback()
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--database", default="lexflow_e2e")
    args = parser.parse_args(argv)
    guard = load_preview_guard()
    url = guard.target_url(args.database, Settings().database_url)
    engine = create_engine(url)
    try:
        with Session(engine) as session:
            connected = session.scalar(text("SELECT current_database()"))
            if connected != args.database:
                raise SystemExit(f"Refusing: connected to {connected!r}.")
            problems = verify(session, args.manifest)
    finally:
        engine.dispose()
    for problem in problems:
        print("MISMATCH:", problem)
    print(
        "verified: all records match the manifest"
        if not problems
        else f"{len(problems)} problem(s)"
    )
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
