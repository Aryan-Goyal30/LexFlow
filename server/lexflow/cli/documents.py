"""Review and permanently purge deleted documents from the command line.

    python -m lexflow.cli.documents list-deleted [--case LF-2026-0001]
    python -m lexflow.cli.documents purge --older-than-days 90 [--case LF-2026-0001]
    python -m lexflow.cli.documents purge --document ID [--document ID ...]

Deleting a document in the app only hides it: its record and file are kept so
an Administrator or the lead advocate can restore it. This command is the only
way to remove them for good, and nothing runs it automatically.

``purge`` first shows exactly which documents it would remove and changes
nothing. To go ahead, run the same command again with ``--confirm N``, where N
is the number of documents the preview listed; if the set has changed since
(say, someone restored one), the counts differ and nothing is purged. Only
documents that are deleted are ever purged, and none on archived cases (restore
the case first). Each purge is recorded in the audit log as made from the
command line by the current operating-system user.
"""

from __future__ import annotations

import argparse
import getpass
import sys
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import TextIO

from sqlalchemy import Select, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from lexflow.audit import Actor, AuditLog
from lexflow.config import Settings, get_settings
from lexflow.db import engine_for, get_independent_sessions
from lexflow.models import Case, Document
from lexflow.services import documents as service
from lexflow.services.formatting import format_file_size
from lexflow.storage import LocalDiskStorage, Storage


class CommandError(Exception):
    """A problem to report to the operator (exit status 1)."""


def _deleted(case_number: str | None) -> Select[tuple[Document, Case]]:
    query = (
        select(Document, Case)
        .join(Case, Case.id == Document.case_id)
        .where(Document.deleted_at.is_not(None))
        .order_by(Document.deleted_at, Document.id)
    )
    if case_number:
        query = query.where(Case.case_number == case_number.strip())
    return query


def _table(rows: Sequence[tuple[Document, Case]]) -> list[str]:
    lines = [f"{'CASE':14} {'DELETED':17} {'SIZE':>9}  {'ID':36}  NAME"]
    for document, case in rows:
        deleted = document.deleted_at.strftime("%Y-%m-%d %H:%M") if document.deleted_at else ""
        size = format_file_size(document.size_bytes) if document.size_bytes else "-"
        lines.append(
            f"{case.case_number:14} {deleted:17} {size:>9}  {document.id!s:36}  {document.name}"
        )
    return lines


def cmd_list_deleted(args: argparse.Namespace, session: Session, out: TextIO) -> int:
    rows = session.execute(_deleted(args.case)).tuples().all()
    if not rows:
        print("No deleted documents.", file=out)
        return 0
    print("\n".join(_table(rows)), file=out)
    print(f"{len(rows)} deleted document(s).", file=out)
    return 0


def _candidates(
    args: argparse.Namespace, session: Session, now: datetime
) -> tuple[list[tuple[Document, Case]], int]:
    """The documents a purge would remove, and how many were left out (archived cases)."""
    query = _deleted(args.case)
    if args.document:
        ids: list[uuid.UUID] = []
        for raw in args.document:
            try:
                ids.append(uuid.UUID(raw))
            except ValueError:
                raise CommandError(f"{raw} is not a valid document id.") from None
        for document_id in ids:
            document = session.get(Document, document_id)
            if document is None:
                raise CommandError(f"No document with the id {document_id}.")
            if document.deleted_at is None:
                raise CommandError(
                    f"Document {document_id} is not deleted. Delete it in the app first; "
                    "only deleted documents can be purged."
                )
        query = query.where(Document.id.in_(ids))
    else:
        cutoff = now - timedelta(days=args.older_than_days)
        query = query.where(Document.deleted_at < cutoff)
    rows = session.execute(query).tuples().all()
    kept = [(d, c) for d, c in rows if c.archived_at is None]
    return kept, len(rows) - len(kept)


def cmd_purge(
    args: argparse.Namespace,
    session: Session,
    out: TextIO,
    *,
    storage: Storage,
    audit: AuditLog,
    now: datetime,
) -> int:
    rows, on_archived = _candidates(args, session, now)
    if on_archived:
        print(
            f"{on_archived} deleted document(s) on archived cases are left alone; "
            "restore the case first to purge them.",
            file=out,
        )
    if not rows:
        print("Nothing to purge.", file=out)
        return 0

    print("\n".join(_table(rows)), file=out)
    if args.confirm is None:
        print(
            f"Preview only: nothing was changed. To permanently remove these {len(rows)} "
            f"document(s) and their files, run the same command with --confirm {len(rows)}.",
            file=out,
        )
        return 0
    if args.confirm != len(rows):
        raise CommandError(
            f"--confirm {args.confirm} does not match the {len(rows)} document(s) listed; "
            "nothing was purged. Check the preview again."
        )

    actor = Actor.command_line(getpass.getuser())
    targets = [(document.id, case.id, case.case_number) for document, case in rows]
    session.rollback()  # end the read transaction; each purge commits on its own
    purged = 0
    for document_id, case_id, case_number in targets:
        if service.purge(session, storage, document_id):
            purged += 1
            audit.record(
                "document.purged",
                actor=actor,
                target_type="document",
                target_id=document_id,
                case_id=case_id,
                details={"caseNumber": case_number},
            )
        else:
            print(f"Skipped {document_id}: it is no longer deleted.", file=out)
    print(f"Purged {purged} document(s) permanently.", file=out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m lexflow.cli.documents",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True)

    listing = commands.add_parser("list-deleted", help="list deleted documents")
    listing.add_argument("--case", help="only this case number, e.g. LF-2026-0001")

    purge = commands.add_parser(
        "purge", help="permanently remove deleted documents (preview first)"
    )
    which = purge.add_mutually_exclusive_group(required=True)
    which.add_argument(
        "--older-than-days",
        type=int,
        metavar="N",
        help="documents deleted more than N days ago",
    )
    which.add_argument(
        "--document", action="append", metavar="ID", help="this deleted document (repeatable)"
    )
    purge.add_argument("--case", help="only this case number")
    purge.add_argument(
        "--confirm",
        type=int,
        metavar="N",
        help="go ahead; N must equal the number of documents the preview listed",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    out: TextIO = sys.stdout,
    now: datetime | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "purge" and args.older_than_days is not None and args.older_than_days < 0:
        print("--older-than-days cannot be negative.", file=sys.stderr)
        return 1
    settings: Settings = get_settings()
    engine = engine_for(settings.database_url)
    try:
        with Session(engine, expire_on_commit=False) as session:
            if args.command == "list-deleted":
                return cmd_list_deleted(args, session, out)
            return cmd_purge(
                args,
                session,
                out,
                storage=LocalDiskStorage(settings.upload_dir),
                audit=AuditLog(get_independent_sessions(engine)),
                now=now or datetime.now(UTC),
            )
    except CommandError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except DBAPIError:
        print(
            "The database could not be used: is it running, and are the migrations "
            "applied (alembic upgrade head)?",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
