"""Validate extraction, pages and chunks of the imported genuine judgments (Batch 3, M5).

    .venv\\Scripts\\python scripts/validate_document_intelligence.py MANIFEST
        [--database lexflow_e2e] [--out DIR]

Read-only (same database guards as ``preview_judgment_import.py``). For every
judgment of the manifest:

1. **Re-extraction:** the stored sections equal a fresh extraction of the
   file (same text, same page numbers), so what is searched is what the
   file holds.
2. **Pages:** sections = PDF pages = the recorded page count.
3. **Printed page markers:** where a page prints "Page N of M" (or "N of M"
   at its head or foot), N equals the stored page number. This checks page
   attribution against the document itself, not only against the extractor.
4. **Chunks:** every chunk's text is exactly ``section[char_start:char_end]``
   of the section it names, carries that section's page number, and the
   chunks of a section leave no gap in its non-blank text.
5. **Hash:** the judgment's content hash is the file's SHA-256.

Writes ``document-intelligence.json`` and ``.md``. Exit status 1 on any
failure. No OCR is attempted: LexFlow has none.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

SERVER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_ROOT))

from lexflow.config import Settings  # noqa: E402
from lexflow.demo import DEMO_MARKER  # noqa: E402
from lexflow.extraction import Limits, extract  # noqa: E402
from lexflow.models import Judgment, JudgmentChunk, JudgmentSection  # noqa: E402
from lexflow.services import judgment_import as importer  # noqa: E402

LIMITS = Limits(max_pages=1000, max_text_bytes=20_000_000, max_unpacked_bytes=200_000_000)
# "Page 3 of 28", "3 of 28", "Page 3": a page number printed by the document.
MARKER = re.compile(
    r"(?:\bPage\s+(\d{1,3})\s+of\s+(\d{1,3})\b|^\s*(\d{1,3})\s+of\s+(\d{1,3})\b)", re.I
)


def guard_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "lexflow_preview_guard", SERVER_ROOT / "scripts" / "preview_judgment_import.py"
    )
    if spec is None or spec.loader is None:
        raise SystemExit("Cannot load the database guard.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def printed_pages(page_text: str) -> set[int]:
    """Page numbers the page prints about itself ("Page N of M")."""
    found: set[int] = set()
    for line in page_text.splitlines():
        for m in MARKER.finditer(line):
            number = m.group(1) or m.group(3)
            if number:
                found.add(int(number))
    return found


def check(session: Session, folder: Path, source: str, entry: dict[str, Any]) -> dict[str, Any]:
    jid = importer.judgment_id(source, entry["id"])
    judgment = session.get(Judgment, jid)
    result: dict[str, Any] = {
        "id": entry["id"],
        "title": entry["title"],
        "problems": [],
        "warnings": [],
    }
    problems: list[str] = result["problems"]
    if judgment is None:
        problems.append("not imported")
        return result
    data = (folder / entry["file"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != judgment.content_sha256:
        problems.append("content hash differs from the file")
    stored = list(
        session.scalars(
            select(JudgmentSection)
            .where(JudgmentSection.judgment_id == jid)
            .order_by(JudgmentSection.number)
        )
    )
    fresh = extract("application/pdf", data, LIMITS).sections
    result["pages"] = len(fresh)
    if len(stored) != len(fresh) or judgment.page_count != len(fresh):
        problems.append(
            f"pages: stored {len(stored)}, recorded {judgment.page_count}, file {len(fresh)}"
        )
    for s, f in zip(stored, fresh, strict=False):
        if s.text != f.text or s.page_number != f.page_number:
            problems.append(
                f"section {s.number}: stored text or page differs from a fresh extraction"
            )
    checked = agreed = 0
    offsets: set[int] = set()
    for s in stored:
        marks = printed_pages(s.text)
        if marks and s.page_number is not None:
            checked += 1
            if s.page_number in marks:
                agreed += 1
            elif len(marks) == 1:
                offsets.add(s.page_number - next(iter(marks)))
            else:
                offsets.add(10_000)  # several different printed numbers: not one offset
    result["printed_markers"] = {"pages_with_marker": checked, "agree": agreed}
    if checked > agreed:
        if len(offsets) == 1 and 10_000 not in offsets and agreed == 0:
            shift = next(iter(offsets))
            result["warnings"].append(
                f"the document's printed page numbers run {shift} behind the PDF pages "
                f"(on all {checked} numbered pages, e.g. an unnumbered cover page): LexFlow "
                "references are PDF pages, so its page N is printed page N - "
                f"{shift}"
            )
        else:
            problems.append(
                f"printed page markers disagree on {checked - agreed} of {checked} pages"
            )
    by_number = {s.number: s for s in stored}
    chunks = list(
        session.scalars(
            select(JudgmentChunk)
            .where(JudgmentChunk.judgment_id == jid)
            .order_by(JudgmentChunk.number)
        )
    )
    result["chunks"] = len(chunks)
    covered: dict[int, list[tuple[int, int]]] = {}
    bad_slices = 0
    for c in chunks:
        section = by_number.get(c.section_number)
        if section is None:
            problems.append(f"chunk {c.number}: names a missing section {c.section_number}")
            continue
        if (
            section.text[c.char_start : c.char_end] != c.text
            or c.page_number != section.page_number
        ):
            bad_slices += 1
        covered.setdefault(section.number, []).append((c.char_start, c.char_end))
    if bad_slices:
        problems.append(f"{bad_slices} chunk(s) are not the exact slice of their page")
    gaps = 0
    for number, section in by_number.items():
        ranges = sorted(covered.get(number, []))
        position = 0
        for start, end in ranges:
            if section.text[position:start].strip():
                gaps += 1
            position = max(position, end)
        if section.text[position:].strip():
            gaps += 1
    if gaps:
        problems.append(f"{gaps} stretch(es) of page text belong to no chunk")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--database", default="lexflow_e2e")
    parser.add_argument("--out", type=Path, default=SERVER_ROOT.parent / "docs/verification/batch3")
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifest.read_bytes())
    url = guard_module().target_url(args.database, Settings().database_url)
    engine = create_engine(url)
    results: list[dict[str, Any]] = []
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
            for entry in manifest["judgments"]:
                results.append(
                    check(session, args.manifest.parent, manifest["source"]["key"], entry)
                )
            session.rollback()
    finally:
        engine.dispose()
    failed = [r for r in results if r["problems"]]
    marked = sum(r.get("printed_markers", {}).get("pages_with_marker", 0) for r in results)
    agreed = sum(r.get("printed_markers", {}).get("agree", 0) for r in results)
    report = {
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "database": args.database,
        "judgments": len(results),
        "pages": sum(r.get("pages", 0) for r in results),
        "chunks": sum(r.get("chunks", 0) for r in results),
        "pages_with_printed_marker": marked,
        "printed_markers_agreeing": agreed,
        "failed": len(failed),
        "warnings": sum(len(r["warnings"]) for r in results),
        "results": results,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "document-intelligence.json").write_text(
        json.dumps(report, indent=1) + "\n", encoding="utf-8"
    )
    lines = [
        "# Document intelligence check on the genuine corpus (generated)",
        "",
        f"Run {report['run_at']} on `{args.database}` (read-only): "
        f"{report['judgments']} judgments, "
        f"{report['pages']} pages, {report['chunks']} chunks.",
        f"Printed page markers: {marked} pages print one; "
        f"{agreed} agree with the stored page number.",
        f"Judgments with a problem: {len(failed)}; warnings: {report['warnings']}.",
        "",
        "| Judgment | Pages | Chunks | Pages with marker | Agreeing | Problems |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        pm = r.get("printed_markers", {})
        lines.append(
            f"| {r['title']} | {r.get('pages', '-')} | {r.get('chunks', '-')} | "
            f"{pm.get('pages_with_marker', '-')} | {pm.get('agree', '-')} | "
            f"{'; '.join(r['problems'] + r['warnings']) or '-'} |"
        )
    (args.out / "document-intelligence.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:5]))
    for r in failed:
        print("PROBLEM:", r["title"], "|", "; ".join(r["problems"]))
    for r in results:
        for warning in r["warnings"]:
            print("WARNING:", r["title"], "|", warning)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
