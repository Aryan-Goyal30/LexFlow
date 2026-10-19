"""Review and permanently purge deleted documents; queue older files for text extraction.

    python -m lexflow.cli.documents list-deleted [--case LF-2026-0001]
    python -m lexflow.cli.documents purge --older-than-days 90 [--case LF-2026-0001]
    python -m lexflow.cli.documents purge --document ID [--document ID ...]
    python -m lexflow.cli.documents queue-extraction [--case LF-2026-0001] [--confirm N]

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

``queue-extraction`` finds stored files that have never been queued for text
extraction (uploaded before it existed) and, the same way (preview first, then
``--confirm N``), queues them for the worker (``python -m lexflow.worker``).
It changes no document and never touches a job that already exists. Each
document queued is recorded in the audit log.
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
from lexflow.models import Case, Document, DocumentExtraction
from lexflow.services import documents as service
from lexflow.services import extraction_queue
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


def _never_queued(case_number: str | None) -> Select[tuple[Document, Case]]:
    """Stored files without an extraction job (deleted ones too, for when restored)."""
    query = (
        select(Document, Case)
        .join(Case, Case.id == Document.case_id)
        .outerjoin(DocumentExtraction, DocumentExtraction.document_id == Document.id)
        .where(Document.storage_key.is_not(None), DocumentExtraction.document_id.is_(None))
        .order_by(Case.case_number, Document.id)
    )
    if case_number:
        query = query.where(Case.case_number == case_number.strip())
    return query


def cmd_queue_extraction(
    args: argparse.Namespace, session: Session, out: TextIO, *, audit: AuditLog, now: datetime
) -> int:
    rows = session.execute(_never_queued(args.case)).tuples().all()
    if not rows:
        print("Every stored file has been queued for text extraction already.", file=out)
        return 0
    lines = [f"{'CASE':14} {'TYPE':28} {'ID':36}  NAME"]
    lines += [
        f"{case.case_number:14} {document.content_type or '':28} {document.id!s:36}  "
        f"{document.name}"
        for document, case in rows
    ]
    print("\n".join(lines), file=out)
    if args.confirm is None:
        print(
            f"Preview only: nothing was changed. To queue these {len(rows)} document(s) for "
            f"text extraction, run the same command with --confirm {len(rows)}.",
            file=out,
        )
        return 0
    if args.confirm != len(rows):
        raise CommandError(
            f"--confirm {args.confirm} does not match the {len(rows)} document(s) listed; "
            "nothing was queued. Check the preview again."
        )

    queued: list[tuple[uuid.UUID, uuid.UUID, str, str]] = []
    for document, case in rows:
        # Lock the document as the app's retry does, then check again: someone
        # may have asked for its extraction since the preview.
        session.refresh(document, with_for_update=True)
        if session.get(DocumentExtraction, document.id) is not None:
            continue
        job = extraction_queue.queue(session, document, requested_by=None, now=now)
        queued.append((document.id, case.id, case.case_number, job.status))
    session.commit()

    actor = Actor.command_line(getpass.getuser())
    for document_id, case_id, case_number, status in queued:
        audit.record(
            "document.extraction_queued",
            actor=actor,
            target_type="document",
            target_id=document_id,
            case_id=case_id,
            details={"caseNumber": case_number, "status": status},
        )
    waiting = sum(1 for *_, status in queued if status == "queued")
    print(
        f"Queued {waiting} document(s) for text extraction; "
        f"{len(queued) - waiting} are file types that are not extracted. "
        "The worker (python -m lexflow.worker) processes them.",
        file=out,
    )
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

    backfill = commands.add_parser(
        "queue-extraction",
        help="queue stored files that were never queued for text extraction (preview first)",
    )
    backfill.add_argument("--case", help="only this case number")
    backfill.add_argument(
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
            if args.command == "queue-extraction":
                return cmd_queue_extraction(
                    args,
                    session,
                    out,
                    audit=AuditLog(get_independent_sessions(engine)),
                    now=now or datetime.now(UTC),
                )
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
