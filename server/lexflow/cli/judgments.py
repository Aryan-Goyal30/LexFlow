"""Manage the judgment collection from the command line (Phase 4).

    python -m lexflow.cli.judgments import FOLDER/manifest.json            # preview
    python -m lexflow.cli.judgments import FOLDER/manifest.json --confirm N
    python -m lexflow.cli.judgments import … --update      # also replace changed files
    python -m lexflow.cli.judgments sources                                # sources and their terms
    python -m lexflow.cli.judgments index [--confirm N]                    # embeddings (if enabled)
    python -m lexflow.cli.judgments remove --source KEY [--confirm N]      # e.g. licence withdrawn

Judgments come only from files the operator supplies, with a manifest that
records their source and its terms of use (``lexflow/services/
judgment_import.py``). Every command previews first and changes nothing
until ``--confirm N`` matches the number previewed. Synthetic (invented)
sources are refused unless ``--allow-synthetic`` is given and the database
is a test database (its name contains "test" or "e2e"). Each import, removal
and indexing run is recorded in the audit log as made from the command line.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from sqlalchemy import delete, func, make_url, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from lexflow.audit import Actor, AuditLog
from lexflow.config import Settings, get_settings
from lexflow.db import engine_for, get_independent_sessions
from lexflow.embeddings import EmbeddingsUnavailableError, provider_for
from lexflow.extraction import Extracted, Limits
from lexflow.extraction.runner import run_extraction
from lexflow.models import Judgment, JudgmentSource
from lexflow.services import judgment_import as importer
from lexflow.services import judgments as service

DB_MESSAGE = (
    "The database could not be used: is it running, and are the migrations applied "
    "(alembic upgrade head)?"
)


class CommandError(Exception):
    """A problem to report to the operator (exit status 1)."""


def _confirm(args: argparse.Namespace, count: int, what: str, out: TextIO) -> bool:
    """True to go ahead; prints the preview line otherwise. Raises on a wrong count."""
    if args.confirm is None:
        print(
            f"Preview only: nothing was changed. To {what} these {count}, run the same "
            f"command with --confirm {count}.",
            file=out,
        )
        return False
    if args.confirm != count:
        raise CommandError(
            f"--confirm {args.confirm} does not match the {count} listed; nothing was changed."
        )
    return True


def _extract(content_type: str, data: bytes, limits: Limits, timeout: float) -> Extracted:
    return run_extraction(content_type, data, limits, timeout_seconds=timeout)


def cmd_import(
    args: argparse.Namespace,
    settings: Settings,
    session: Session,
    out: TextIO,
    *,
    audit: AuditLog,
    now: datetime,
    extract: importer.ExtractFn = _extract,
) -> int:
    try:
        plan = importer.plan_import(
            session, Path(args.manifest), max_bytes=settings.max_upload_bytes
        )
    except importer.ManifestError as exc:
        raise CommandError(str(exc)) from exc
    source = plan.manifest.source
    if source.synthetic:
        database = make_url(settings.database_url).database or ""
        if not args.allow_synthetic:
            raise CommandError(
                f"Source {source.key!r} is synthetic (invented test data); it is only imported "
                "into test databases, with --allow-synthetic."
            )
        if "test" not in database and "e2e" not in database:
            raise CommandError(
                "Synthetic judgments are never imported into this database "
                "(only into databases whose name contains 'test' or 'e2e')."
            )
    print(
        f"Source: {source.name} ({source.key})"
        f"{' [SYNTHETIC TEST DATA]' if source.synthetic else ''}",
        file=out,
    )
    print(
        f"Terms: {source.terms_url} — checked {source.terms_checked_on} by "
        f"{source.terms_checked_by}",
        file=out,
    )
    if plan.source_change:
        print(f"Source record: {plan.source_change}", file=out)
    for item in plan.items:
        reason = f" — {item.reason}" if item.reason else ""
        print(f"  {item.status:9} {item.entry.id}  {item.entry.title}{reason}", file=out)
    to_do = plan.count("new") + (plan.count("changed") if args.update else 0)
    print(
        f"{plan.count('new')} new, {plan.count('changed')} changed"
        f"{'' if args.update else ' (left alone without --update)'}, "
        f"{plan.count('unchanged')} unchanged, {plan.count('duplicate')} duplicate, "
        f"{plan.count('invalid')} invalid.",
        file=out,
    )
    if to_do == 0:
        print("Nothing to import.", file=out)
        return 0
    if not _confirm(args, to_do, "import", out):
        return 0
    operator = getpass.getuser()
    outcome = importer.apply_import(
        session,
        plan,
        update=args.update,
        limits=Limits(
            max_pages=settings.extraction_max_pages,
            max_text_bytes=settings.extraction_max_text_bytes,
            max_unpacked_bytes=settings.extraction_max_unpacked_bytes,
        ),
        timeout_seconds=settings.extraction_timeout_seconds,
        extract=extract,
        operator=f"command line ({operator})",
        now=now,
    )
    actor = Actor.command_line(operator)
    for status, ids in (("new", outcome.imported), ("updated", outcome.updated)):
        for judgment_id in ids:
            audit.record(
                "judgment.imported",
                actor=actor,
                target_type="judgment",
                target_id=judgment_id,
                details={"source": source.key, "status": status},
            )
    for manifest_id, reason in outcome.rejected:
        print(f"  rejected  {manifest_id} — {reason}", file=out)
    print(
        f"Imported {len(outcome.imported)}, updated {len(outcome.updated)}, "
        f"rejected {len(outcome.rejected)}.",
        file=out,
    )
    return 0 if not outcome.rejected else 1


def cmd_sources(session: Session, out: TextIO) -> int:
    rows = session.execute(
        select(JudgmentSource, func.count(Judgment.id))
        .outerjoin(Judgment, Judgment.source_id == JudgmentSource.id)
        .group_by(JudgmentSource.id)
        .order_by(JudgmentSource.key)
    ).all()
    if not rows:
        print("No judgment sources recorded; the collection is empty.", file=out)
        return 0
    for source, judgments in rows:
        flag = " [SYNTHETIC]" if source.is_synthetic else ""
        print(f"{source.key}{flag}: {source.name} — {judgments} judgment(s)", file=out)
        print(
            f"  terms {source.terms_url}, checked {source.terms_checked_on} by "
            f"{source.terms_checked_by}",
            file=out,
        )
        print(f"  permitted use: {source.permitted_use}", file=out)
    return 0


def cmd_index(
    args: argparse.Namespace,
    settings: Settings,
    session: Session,
    out: TextIO,
    *,
    audit: AuditLog,
) -> int:
    try:
        provider = provider_for(settings)
    except EmbeddingsUnavailableError as exc:
        raise CommandError(str(exc)) from exc
    if provider is None:
        raise CommandError(
            "Embeddings are disabled (LEXFLOW_EMBEDDINGS); judgments are searched by keyword."
        )
    waiting = service.needing_vectors(session, provider.model)
    if not waiting:
        print(f"Every judgment has vectors for {provider.model}.", file=out)
        return 0
    for judgment_id, title in waiting:
        print(f"  {judgment_id}  {title}", file=out)
    if not _confirm(args, len(waiting), "embed", out):
        return 0
    embedded = 0
    for judgment_id, _ in waiting:
        embedded += service.index_judgment(
            session,
            provider,
            judgment_id,
            batch_size=settings.embedding_batch_size,
            now=lambda: datetime.now(UTC),
        )
    audit.record(
        "judgments.indexed",
        actor=Actor.command_line(getpass.getuser()),
        target_type="judgment",
        details={"judgments": len(waiting), "chunks": embedded},
    )
    print(f"Indexed {len(waiting)} judgment(s): {embedded} chunk(s) embedded.", file=out)
    return 0


def cmd_remove(args: argparse.Namespace, session: Session, out: TextIO, *, audit: AuditLog) -> int:
    source = session.scalar(select(JudgmentSource).where(JudgmentSource.key == args.source))
    if source is None:
        raise CommandError(f"No source with the key {args.source!r}.")
    ids = list(session.scalars(select(Judgment.id).where(Judgment.source_id == source.id)))
    print(f"Source {source.key}: {len(ids)} judgment(s) and their text would be removed.", file=out)
    if not ids:
        return 0
    if not _confirm(args, len(ids), "remove", out):
        return 0
    session.execute(delete(Judgment).where(Judgment.source_id == source.id))
    session.commit()
    actor = Actor.command_line(getpass.getuser())
    audit.record(
        "judgment.removed",
        actor=actor,
        target_type="judgment_source",
        details={"source": source.key, "judgments": len(ids)},
    )
    print(f"Removed {len(ids)} judgment(s) of {source.key}.", file=out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m lexflow.cli.judgments",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True)

    def confirm(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--confirm",
            type=int,
            metavar="N",
            help="go ahead; N must equal the number the preview listed",
        )

    imp = commands.add_parser("import", help="import judgments from a manifest (preview first)")
    imp.add_argument("manifest", help="path to manifest.json")
    imp.add_argument(
        "--update", action="store_true", help="also replace judgments whose file changed"
    )
    imp.add_argument(
        "--allow-synthetic",
        action="store_true",
        help="accept a synthetic source (test databases only)",
    )
    confirm(imp)
    commands.add_parser("sources", help="list sources and their terms-of-use records")
    confirm(commands.add_parser("index", help="embed judgments (needs LEXFLOW_EMBEDDINGS=local)"))
    remove = commands.add_parser("remove", help="remove every judgment of a source (preview first)")
    remove.add_argument("--source", required=True, help="the source key")
    confirm(remove)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    out: TextIO = sys.stdout,
    now: datetime | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    settings = get_settings()
    engine = engine_for(settings.database_url)
    audit = AuditLog(get_independent_sessions(engine))
    try:
        with Session(engine, expire_on_commit=False) as session:
            if args.command == "import":
                return cmd_import(
                    args, settings, session, out, audit=audit, now=now or datetime.now(UTC)
                )
            if args.command == "sources":
                return cmd_sources(session, out)
            if args.command == "index":
                return cmd_index(args, settings, session, out, audit=audit)
            return cmd_remove(args, session, out, audit=audit)
    except CommandError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except DBAPIError:
        print(DB_MESSAGE, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
