"""Preview a judgment import against a test or demo database, changing nothing.

    .venv\\Scripts\\python scripts/preview_judgment_import.py MANIFEST
        [--database lexflow_e2e] [--out PREVIEW.md]

What the import CLI would do (new, unchanged, changed, duplicate or invalid,
with reasons), plus what the real extractor reads from every file (pages,
characters, empty pages), the source record and the attribution, written as
Markdown for the owner to approve. It never imports.

Safety:
- the database is named here, never taken from DATABASE_URL: it must have
  "test" or "e2e" as a name part and must not be the DATABASE_URL database
  (the live one), and a URL ``dbname``/``service`` parameter is refused;
- the connection must report that name (``current_database()``), and an
  "e2e" database must carry the isolated-demo marker;
- planning runs in a READ ONLY transaction that is rolled back.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine, make_url, text
from sqlalchemy.orm import Session

SERVER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_ROOT))

from lexflow.config import Settings, is_test_database_name  # noqa: E402
from lexflow.demo import DEMO_MARKER  # noqa: E402
from lexflow.extraction import Limits, extract  # noqa: E402
from lexflow.services import judgment_import as importer  # noqa: E402


def target_url(name: str, configured: str) -> str:
    base = make_url(configured)
    if {"dbname", "service"} & set(base.query):
        raise SystemExit("Refusing a DATABASE_URL with a dbname or service parameter.")
    if not is_test_database_name(name):
        raise SystemExit(f"Refusing {name!r}: only a test or e2e database may be previewed.")
    if name == base.database:
        raise SystemExit(f"Refusing {name!r}: it is the DATABASE_URL (live) database.")
    return base.set(database=name).render_as_string(hide_password=False)


def preview(manifest: Path, session: Session, database: str, max_bytes: int) -> list[str]:
    connected, marker = session.execute(
        text(
            "SELECT current_database(), shobj_description(oid, 'pg_database') "
            "FROM pg_database WHERE datname = current_database()"
        )
    ).one()
    if connected != database:
        raise SystemExit(f"Refusing: connected to {connected!r}, not {database!r}.")
    if "e2e" in database and marker != DEMO_MARKER:
        raise SystemExit("Refusing: the e2e database does not carry the isolated-demo marker.")
    session.execute(text("SET TRANSACTION READ ONLY"))
    plan = importer.plan_import(session, manifest, max_bytes=max_bytes)
    source = plan.manifest.source
    limits = Limits(max_pages=1000, max_text_bytes=20_000_000, max_unpacked_bytes=200_000_000)
    lines = [
        f"Database: `{connected}` (read-only transaction, rolled back; nothing imported)",
        f"Manifest: `{manifest.name}`, format `{plan.manifest.format}`, "
        f"SHA-256 `{plan.manifest_sha256}`",
        f"Source: {source.name} (`{source.key}`){' [SYNTHETIC]' if source.synthetic else ''}",
        f"Terms: {source.terms_url}, checked {source.terms_checked_on} "
        f"by {source.terms_checked_by}",
        f"Licence: {source.licence or '(none stated)'}",
        f"Attribution shown with every judgment: {source.attribution or '(none)'}",
        f"Source record: {plan.source_change or 'already present, unchanged'}",
        "",
        "| # | Status | Id | Title | Date | Neutral citation | Citation | SHA-256 (import copy) "
        "| Pages | Characters | Empty pages | Issues |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    issues_total = 0
    for n, item in enumerate(plan.items, start=1):
        entry = item.entry
        issues: list[str] = [item.reason] if item.reason else []
        pages = chars = empty = "-"
        if item.path is not None and item.status in ("new", "changed", "unchanged"):
            got = extract("application/pdf", item.path.read_bytes(), limits)
            sections = got.sections
            pages = str(len(sections))
            chars = str(sum(len(s.text) for s in sections))
            blank = [
                s.page_number or i for i, s in enumerate(sections, start=1) if not s.text.strip()
            ]
            empty = str(len(blank))
            if blank:
                issues.append(f"no text layer on page(s) {', '.join(map(str, blank[:8]))}")
        if not entry.neutral_citation and not entry.citation:
            issues.append("no citation printed in the document (left blank)")
        issues_total += bool(issues)
        lines.append(
            f"| {n} | {item.status} | `{entry.id}` | {entry.title} | "
            f"{entry.decision_date or '-'} | {entry.neutral_citation or '-'} | "
            f"{entry.citation or '-'} | `{item.sha256[:16]}…` | {pages} | {chars} | {empty} | "
            f"{'; '.join(issues) or '-'} |"
        )
    lines += ["", "## Each document", ""]
    for n, item in enumerate(plan.items, start=1):
        entry, record = item.entry, item.entry.provenance
        lines += [
            f"### {n}. {entry.title}",
            "",
            f"- Id: `{entry.id}`; status: {item.status}",
            f"- Court and date: {entry.court}, {entry.decision_date or 'date not recorded'}",
            f"- Neutral citation: {entry.neutral_citation or '(none printed)'}; "
            f"other citation: {entry.citation or '(none printed)'}",
            f"- Source URL: {entry.source_url}",
            f"- File: `{entry.file}`, SHA-256 `{item.sha256}`",
        ]
        if record.get("original_sha256"):
            same = record["original_sha256"] == item.sha256
            lines.append(
                f"- Original as served: SHA-256 `{record['original_sha256']}`"
                + ("" if same else f"; change: {record.get('original_transform', '(not stated)')}")
            )
        for key, label in (
            ("retrieved_at", "Retrieved"),
            ("corpus_role", "Role"),
            ("selected_by", "Prepared by"),
            ("legal_review", "Legal review"),
            ("notes", "Notes"),
        ):
            if record.get(key):
                lines.append(f"- {label}: {record[key]}")
        lines.append("")
    lines += [
        "",
        f"{plan.count('new')} new, {plan.count('changed')} changed, "
        f"{plan.count('unchanged')} unchanged, {plan.count('duplicate')} duplicate, "
        f"{plan.count('invalid')} invalid; {issues_total} with notes.",
    ]
    session.rollback()
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--database", default="lexflow_e2e")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    settings = Settings()
    engine = create_engine(target_url(args.database, settings.database_url))
    try:
        with Session(engine) as session:
            lines = preview(args.manifest, session, args.database, settings.max_upload_bytes)
    finally:
        engine.dispose()
    report = "\n".join(lines) + "\n"
    if args.out:
        args.out.write_text(report, encoding="utf-8")
        print(f"wrote {args.out}")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
