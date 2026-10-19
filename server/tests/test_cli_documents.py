"""The purge command line (``python -m lexflow.cli.documents``).

The command opens its own database connection and commits, like an operator's
shell would, so these tests use ``committed_engine`` (cleaned up afterwards).
Files go to the test upload directory from ``LEXFLOW_UPLOAD_DIR``.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from lexflow.cli.documents import main
from lexflow.config import get_settings
from lexflow.models import AuditEvent, Case, Document
from lexflow.seed import sample_uuid
from lexflow.seed.loader import load_sample_data
from lexflow.storage import LocalDiskStorage
from tests.conftest import SERVER_ROOT

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
SATTVIK = sample_uuid("case", "case-1005")


class Docs:
    """Documents with stored files, deleted (or not) at chosen times."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.storage = LocalDiskStorage(get_settings().upload_dir)

    def add(
        self, name: str, *, deleted_days_ago: int | None, case_id: uuid.UUID = SATTVIK
    ) -> uuid.UUID:
        key = self.storage.new_key()
        staged = self.storage.root / f"staged-{key}"
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_bytes(b"%PDF-1.4\n%%EOF\n")
        self.storage.put(key, staged)
        with Session(self.engine) as session, session.begin():
            document = Document(
                case_id=case_id,
                name=name,
                document_type="PDF",
                content_type="application/pdf",
                size_bytes=15,
                sha256="0" * 64,
                storage_key=key,
                uploaded_on=date(2026, 1, 5),
                deleted_at=(
                    NOW - timedelta(days=deleted_days_ago) if deleted_days_ago is not None else None
                ),
            )
            session.add(document)
            session.flush()
            return document.id

    def exists(self, document_id: uuid.UUID) -> bool:
        with Session(self.engine) as session:
            return session.get(Document, document_id) is not None

    def has_file(self, document_id: uuid.UUID) -> bool:
        with Session(self.engine) as session:
            document = session.get(Document, document_id)
            return document is not None and self.storage.exists(document.storage_key or "")

    def key(self, document_id: uuid.UUID) -> str:
        with Session(self.engine) as session:
            document = session.get(Document, document_id)
            assert document is not None and document.storage_key is not None
            return document.storage_key


@pytest.fixture
def docs(committed_engine: Engine) -> Docs:
    with Session(committed_engine) as session, session.begin():
        load_sample_data(session)
    return Docs(committed_engine)


def run(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    code = main(list(argv), out=out, now=NOW)
    return code, out.getvalue()


def purge_audits(engine: Engine) -> list[AuditEvent]:
    with Session(engine) as session:
        return list(
            session.scalars(select(AuditEvent).where(AuditEvent.action == "document.purged"))
        )


def test_purge_previews_first_and_changes_nothing(docs: Docs, committed_engine: Engine) -> None:
    old = docs.add("Old.pdf", deleted_days_ago=120)

    code, out = run("purge", "--older-than-days", "90")

    assert code == 0
    assert "Old.pdf" in out and str(old) in out
    assert "Preview only: nothing was changed." in out
    assert "--confirm 1" in out
    assert docs.exists(old) and docs.has_file(old)
    assert purge_audits(committed_engine) == []


def test_purge_with_the_confirmed_count_removes_record_and_file(
    docs: Docs, committed_engine: Engine
) -> None:
    old = docs.add("Old.pdf", deleted_days_ago=120)
    recent = docs.add("Recent.pdf", deleted_days_ago=10)
    live = docs.add("Live.pdf", deleted_days_ago=None)
    old_key = docs.key(old)

    code, out = run("purge", "--older-than-days", "90", "--confirm", "1")

    assert code == 0, out
    assert "Purged 1 document(s) permanently." in out
    assert not docs.exists(old)
    assert docs.exists(recent) and docs.has_file(recent)
    assert docs.exists(live) and docs.has_file(live)
    assert not docs.storage.exists(old_key)
    [event] = purge_audits(committed_engine)
    assert event.target_id == old
    assert (event.actor_name or "").startswith("command line (")
    assert event.case_id == SATTVIK


def test_a_confirm_count_that_does_not_match_purges_nothing(
    docs: Docs, capsys: pytest.CaptureFixture[str]
) -> None:
    first = docs.add("One.pdf", deleted_days_ago=200)
    second = docs.add("Two.pdf", deleted_days_ago=200)

    code, _ = run("purge", "--older-than-days", "90", "--confirm", "1")

    assert code == 1
    assert "does not match the 2 document(s) listed" in capsys.readouterr().err
    assert docs.exists(first) and docs.exists(second)


def test_a_live_document_is_never_purged(docs: Docs, capsys: pytest.CaptureFixture[str]) -> None:
    live = docs.add("Live.pdf", deleted_days_ago=None)

    code, _ = run("purge", "--document", str(live), "--confirm", "1")

    assert code == 1
    assert "is not deleted" in capsys.readouterr().err
    assert docs.exists(live) and docs.has_file(live)


def test_named_deleted_documents_can_be_purged_whatever_their_age(docs: Docs) -> None:
    today = docs.add("Today.pdf", deleted_days_ago=0)
    code, out = run("purge", "--document", str(today), "--confirm", "1")
    assert code == 0, out
    assert not docs.exists(today)


def test_documents_on_archived_cases_are_left_alone(docs: Docs, committed_engine: Engine) -> None:
    old = docs.add("Old.pdf", deleted_days_ago=120)
    with Session(committed_engine) as session, session.begin():
        case = session.get(Case, SATTVIK)
        assert case is not None
        case.archived_at = NOW

    code, out = run("purge", "--older-than-days", "90", "--confirm", "1")

    assert code == 0
    assert "1 deleted document(s) on archived cases are left alone" in out
    assert "Nothing to purge." in out
    assert docs.exists(old)


def test_list_deleted_shows_only_deleted_documents(docs: Docs) -> None:
    docs.add("Gone.pdf", deleted_days_ago=3)
    docs.add("Live.pdf", deleted_days_ago=None)

    code, out = run("list-deleted")

    assert code == 0
    assert "Gone.pdf" in out and "Live.pdf" not in out
    assert "1 deleted document(s)." in out


def test_negative_ages_are_refused(docs: Docs, capsys: pytest.CaptureFixture[str]) -> None:
    assert run("purge", "--older-than-days", "-1")[0] == 1
    assert "cannot be negative" in capsys.readouterr().err


def test_runs_as_a_module(committed_engine: Engine) -> None:
    environment = {**os.environ, "LEXFLOW_ENV": "test"}
    result = subprocess.run(
        [sys.executable, "-m", "lexflow.cli.documents", "purge", "--help"],
        cwd=SERVER_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--confirm" in result.stdout and "preview" in result.stdout.lower()


def test_uses_the_configured_upload_directory() -> None:
    assert Path(get_settings().upload_dir).is_absolute()
