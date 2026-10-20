"""Importing judgments: provenance, validation, duplicates, synthetic gates.

The fixtures (``tests/fixtures/judgments/synthetic``) are SYNTHETIC: invented
judgments that the importer accepts only into test databases. Commands run
with their own sessions on committed data (``committed_engine``).
"""

from __future__ import annotations

import io
import json
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from lexflow.audit import AuditLog
from lexflow.cli import judgments as cli
from lexflow.config import Settings, get_settings
from lexflow.db import get_independent_sessions
from lexflow.extraction import Extracted, Limits, extract
from lexflow.models import (
    AuditEvent,
    Judgment,
    JudgmentChunk,
    JudgmentChunkEmbedding,
    JudgmentSection,
    JudgmentSource,
)
from lexflow.services import judgment_import as importer
from tests.document_fixtures import pdf_without_text
from tests.embedding_fakes import WordsProvider

FIXTURES = Path(__file__).parent / "fixtures" / "judgments" / "synthetic"
NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def in_process(content_type: str, data: bytes, limits: Limits, timeout: float) -> Extracted:
    return extract(content_type, data, limits)


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    """A private copy of the synthetic fixtures, safe to change."""
    target = tmp_path / "corpus"
    shutil.copytree(FIXTURES, target)
    return target / "manifest.json"


def manifest_of(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def write(path: Path, data: dict[str, Any]) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def run(
    engine: Engine,
    command: str,
    *argv: str,
    settings: Settings | None = None,
    extract_fn: Any = in_process,
) -> tuple[int, str]:
    out = io.StringIO()
    args = cli.build_parser().parse_args([command, *argv])
    audit = AuditLog(get_independent_sessions(engine))
    config = settings or get_settings()
    with Session(engine, expire_on_commit=False) as session:
        if command == "import":
            code = cli.cmd_import(
                args, config, session, out, audit=audit, now=NOW, extract=extract_fn
            )
        elif command == "sources":
            code = cli.cmd_sources(session, out)
        elif command == "index":
            code = cli.cmd_index(args, config, session, out, audit=audit)
        else:
            code = cli.cmd_remove(args, session, out, audit=audit)
    return code, out.getvalue()


def count(engine: Engine, model: Any) -> int:
    with Session(engine) as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


def imported(engine: Engine, corpus: Path) -> None:
    code, out = run(engine, "import", str(corpus), "--allow-synthetic", "--confirm", "13")
    assert code == 0, out


# --- the happy path ---------------------------------------------------------------------


def test_preview_lists_everything_and_changes_nothing(
    committed_engine: Engine, corpus: Path
) -> None:
    code, out = run(committed_engine, "import", str(corpus), "--allow-synthetic")
    assert code == 0
    assert "[SYNTHETIC TEST DATA]" in out and "Source record: new" in out
    assert "13 new, 0 changed" in out and "--confirm 13" in out
    assert count(committed_engine, Judgment) == 0 and count(committed_engine, JudgmentSource) == 0


def test_import_stores_metadata_text_chunks_and_provenance(
    committed_engine: Engine, corpus: Path
) -> None:
    imported(committed_engine, corpus)
    assert count(committed_engine, Judgment) == 13
    with Session(committed_engine) as session:
        expected_id = importer.judgment_id("lexflow-synthetic", "syn-003")
        judgment = session.get(Judgment, expected_id)
        assert judgment is not None
        assert judgment.title == "Golden Grain Foods v. Sunrise Bakers (SYNTHETIC)"
        assert judgment.citation == "(SYN) 2018 TEST 103"
        assert (judgment.decision_date.isoformat(), judgment.year) == ("2018-11-20", 2018)  # type: ignore[union-attr]
        assert judgment.source_url == "https://judgments.lexflow.invalid/syn-003"
        assert judgment.practice_areas == ["Trademark"]
        assert judgment.imported_by.startswith("command line (") and judgment.imported_at == NOW
        assert len(judgment.manifest_sha256) == 64 and judgment.index_status == "disabled"
        section = session.get(JudgmentSection, (expected_id, 1))
        assert section is not None and "deceptively similar" in section.text
        for chunk in session.scalars(
            select(JudgmentChunk).where(JudgmentChunk.judgment_id == expected_id)
        ):
            assert section.text[chunk.char_start : chunk.char_end] == chunk.text
        bare = session.get(Judgment, importer.judgment_id("lexflow-synthetic", "syn-013"))
        assert bare is not None
        assert (bare.citation, bare.decision_date, bare.year, bare.bench) == (
            None,
            None,
            None,
            None,
        )
        assert bare.practice_areas == []
        source = session.scalars(select(JudgmentSource)).one()
        assert source.is_synthetic and source.terms_checked_by == "LexFlow developers"
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.action == "judgment.imported")
        ).all()
    assert len(events) == 13
    assert all(e.details == {"source": "lexflow-synthetic", "status": "new"} for e in events)


def test_ids_are_stable_across_imports(committed_engine: Engine, corpus: Path) -> None:
    assert importer.judgment_id("a-source", "x") == importer.judgment_id("a-source", "x")
    assert importer.judgment_id("a-source", "x") != importer.judgment_id("b-source", "x")
    imported(committed_engine, corpus)
    _, out = run(committed_engine, "import", str(corpus), "--allow-synthetic")
    assert "0 new, 0 changed" in out and "13 unchanged" in out and "Nothing to import" in out


def test_a_changed_file_is_replaced_only_with_update(
    committed_engine: Engine, corpus: Path
) -> None:
    imported(committed_engine, corpus)
    target = corpus.parent / "files" / "syn-001.txt"
    target.write_text(target.read_text(encoding="utf-8") + "\nA corrected paragraph.\n", "utf-8")
    code, out = run(committed_engine, "import", str(corpus), "--allow-synthetic")
    assert "1 changed (left alone without --update)" in out and "Nothing to import" in out
    code, out = run(
        committed_engine, "import", str(corpus), "--allow-synthetic", "--update", "--confirm", "1"
    )
    assert code == 0 and "updated 1" in out
    with Session(committed_engine) as session:
        section = session.get(
            JudgmentSection, (importer.judgment_id("lexflow-synthetic", "syn-001"), 1)
        )
        assert section is not None and "corrected paragraph" in section.text
        updates = session.scalars(
            select(AuditEvent).where(AuditEvent.action == "judgment.imported")
        ).all()
    assert sum(1 for e in updates if e.details["status"] == "updated") == 1


# --- duplicates ---------------------------------------------------------------------------


def test_duplicates_are_reported_not_stored(committed_engine: Engine, corpus: Path) -> None:
    data = manifest_of(corpus)
    data["judgments"] = data["judgments"][:3]
    copy = dict(data["judgments"][0], id="syn-copy", citation=None)  # same file again
    data["judgments"].append(copy)
    _, out = run(committed_engine, "import", str(write(corpus, data)), "--allow-synthetic")
    assert "duplicate syn-copy" in out.replace("  ", " ").replace("  ", " ")
    assert "same file as 'syn-001' in this manifest" in out
    run(committed_engine, "import", str(corpus), "--allow-synthetic", "--confirm", "3")

    other = manifest_of(corpus)
    other["source"]["key"] = "another-synthetic"
    other["judgments"] = [dict(other["judgments"][1], id="elsewhere", citation=None)]
    _, out = run(committed_engine, "import", str(write(corpus, other)), "--allow-synthetic")
    assert "this file is already in the collection" in out

    target = corpus.parent / "files" / "new.txt"
    target.write_text("SYNTHETIC. A different judgment with a clashing citation.", "utf-8")
    other["judgments"] = [
        dict(
            other["judgments"][0], id="clash", file="files/new.txt", citation="(syn) 2019 test 101"
        )
    ]
    _, out = run(committed_engine, "import", str(write(corpus, other)), "--allow-synthetic")
    assert "another judgment has this citation" in out  # compared case-insensitively
    assert count(committed_engine, Judgment) == 3


# --- files ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("file", "reason"),
    [
        ("../../secret.txt", "leaves the manifest's folder"),
        ("files/syn-001.exe", "only .pdf, .docx and .txt"),
        ("files/missing.txt", "does not exist"),
        ("files/empty.txt", "empty or larger than the upload limit"),
    ],
)
def test_bad_files_are_invalid(
    committed_engine: Engine, corpus: Path, file: str, reason: str
) -> None:
    (corpus.parent / "files" / "empty.txt").write_text("", "utf-8")
    (corpus.parent / "files" / "syn-001.exe").write_bytes(b"MZ")
    (corpus.parent.parent / "secret.txt").write_text("outside", "utf-8")
    data = manifest_of(corpus)
    data["judgments"] = [dict(data["judgments"][0], file=file)]
    code, out = run(committed_engine, "import", str(write(corpus, data)), "--allow-synthetic")
    assert code == 0 and "invalid" in out and reason in out and "Nothing to import" in out


def test_a_file_without_text_is_rejected_whole(committed_engine: Engine, corpus: Path) -> None:
    (corpus.parent / "files" / "scan.pdf").write_bytes(pdf_without_text())
    data = manifest_of(corpus)
    data["judgments"] = [
        dict(data["judgments"][0], id="scan", file="files/scan.pdf", citation=None)
    ]
    code, out = run(
        committed_engine, "import", str(write(corpus, data)), "--allow-synthetic", "--confirm", "1"
    )
    assert code == 1 and "rejected  scan — no-text-layer" in out
    assert count(committed_engine, Judgment) == 0 and count(committed_engine, JudgmentSection) == 0


def test_the_real_extractor_runs_in_its_child_process(
    committed_engine: Engine, corpus: Path
) -> None:
    data = manifest_of(corpus)
    data["judgments"] = data["judgments"][:1]
    code, out = run(
        committed_engine,
        "import",
        str(write(corpus, data)),
        "--allow-synthetic",
        "--confirm",
        "1",
        extract_fn=cli._extract,
    )
    assert code == 0 and "Imported 1" in out


# --- manifests ------------------------------------------------------------------------------


def broken(corpus: Path, change: Any) -> str:
    data = manifest_of(corpus)
    change(data)
    return str(write(corpus, data))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: d.update(format="other/9"), "format"),
        (lambda d: d["source"].pop("terms_url"), "terms_url"),
        (lambda d: d["source"].pop("permitted_use"), "permitted_use"),
        (lambda d: d["source"].update(terms_url="http://terms.lexflow.invalid/x"), "https://"),
        (
            lambda d: d["judgments"][0].update(source_url="https://u:p@a.lexflow.invalid/"),
            "credentials",
        ),
        (
            lambda d: d["judgments"][0].update(source_url="https://real-court.example.org/x"),
            ".invalid",
        ),
        (lambda d: d["judgments"][0].update(year=1999), "does not match decision_date"),
        (lambda d: d["judgments"][0].update(id=d["judgments"][1]["id"]), "appears twice"),
        (lambda d: d["judgments"][0].update(surprise=True), "Extra inputs"),
        (lambda d: d["judgments"][0].pop("court"), "court"),
        (lambda d: d["judgments"][0].update(practice_areas=[""]), "practice area"),
        (lambda d: d.update(judgments=[]), "judgments"),
    ],
)
def test_invalid_manifests_import_nothing(
    committed_engine: Engine,
    corpus: Path,
    capsys: pytest.CaptureFixture[str],
    change: Any,
    message: str,
) -> None:
    with pytest.raises(cli.CommandError, match="not a valid manifest") as raised:
        run(
            committed_engine,
            "import",
            broken(corpus, change),
            "--allow-synthetic",
            "--confirm",
            "13",
        )
    assert message in str(raised.value)
    assert count(committed_engine, JudgmentSource) == 0


def test_a_real_source_may_not_use_reserved_test_addresses(corpus: Path) -> None:
    data = manifest_of(corpus)
    data["source"]["synthetic"] = False
    with pytest.raises(importer.ManifestError, match="reserved test address"):
        importer.load_manifest(write(corpus, data))


def test_not_json_is_reported(committed_engine: Engine, corpus: Path) -> None:
    corpus.write_text("{not json", "utf-8")
    with pytest.raises(cli.CommandError, match="not valid UTF-8 JSON"):
        run(committed_engine, "import", str(corpus), "--allow-synthetic")


# --- synthetic data never reaches a real collection --------------------------------------------


def test_synthetic_sources_need_the_explicit_flag(committed_engine: Engine, corpus: Path) -> None:
    with pytest.raises(cli.CommandError, match="only imported into test databases"):
        run(committed_engine, "import", str(corpus), "--confirm", "13")
    assert count(committed_engine, Judgment) == 0


def test_synthetic_sources_are_refused_outside_test_databases(
    committed_engine: Engine, corpus: Path
) -> None:
    live_like = get_settings().model_copy(
        update={"database_url": "postgresql+psycopg://u@127.0.0.1:1/lexflow"}
    )
    with pytest.raises(cli.CommandError, match="never imported into this database"):
        run(committed_engine, "import", str(corpus), "--allow-synthetic", settings=live_like)


def test_a_source_cannot_switch_between_real_and_synthetic(
    committed_engine: Engine, corpus: Path
) -> None:
    imported(committed_engine, corpus)
    data = manifest_of(corpus)
    data["source"]["synthetic"] = False
    data["source"]["terms_url"] = "https://terms.example-court.in/terms"
    for entry in data["judgments"]:
        entry["source_url"] = "https://judgments.example-court.in/" + entry["id"]
    with pytest.raises(cli.CommandError, match="recorded as synthetic"):
        run(committed_engine, "import", str(write(corpus, data)))


def test_a_changed_terms_record_is_stored(committed_engine: Engine, corpus: Path) -> None:
    imported(committed_engine, corpus)
    data = manifest_of(corpus)
    data["source"]["terms_checked_on"] = "2026-11-01"
    target = corpus.parent / "files" / "fresh.txt"
    target.write_text("SYNTHETIC. One more invented order.", "utf-8")
    data["judgments"] = [
        dict(data["judgments"][0], id="fresh", file="files/fresh.txt", citation=None)
    ]
    _, out = run(
        committed_engine, "import", str(write(corpus, data)), "--allow-synthetic", "--confirm", "1"
    )
    assert "Source record: terms record updated" in out
    with Session(committed_engine) as session:
        assert (
            session.scalars(select(JudgmentSource)).one().terms_checked_on.isoformat()
            == "2026-11-01"
        )


# --- sources, indexing and removal -------------------------------------------------------------


def test_sources_lists_terms_and_counts(committed_engine: Engine, corpus: Path) -> None:
    assert "the collection is empty" in run(committed_engine, "sources")[1]
    imported(committed_engine, corpus)
    out = run(committed_engine, "sources")[1]
    assert "lexflow-synthetic [SYNTHETIC]: LexFlow synthetic test judgments — 13 judgment(s)" in out
    assert "terms https://terms.lexflow.invalid/synthetic" in out and "permitted use:" in out


def test_indexing_needs_embeddings_and_previews(
    committed_engine: Engine, corpus: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    imported(committed_engine, corpus)
    with pytest.raises(cli.CommandError, match="Embeddings are disabled"):
        run(committed_engine, "index")
    provider = WordsProvider()
    monkeypatch.setattr(cli, "provider_for", lambda settings: provider)
    code, out = run(committed_engine, "index")
    assert "--confirm 13" in out and count(committed_engine, JudgmentChunkEmbedding) == 0
    code, out = run(committed_engine, "index", "--confirm", "13")
    assert code == 0 and "Indexed 13 judgment(s)" in out
    assert count(committed_engine, JudgmentChunkEmbedding) == count(committed_engine, JudgmentChunk)
    with Session(committed_engine) as session:
        statuses = set(session.scalars(select(Judgment.embedding_model)))
    assert statuses == {provider.model}
    assert "Every judgment has vectors" in run(committed_engine, "index")[1]


def test_removing_a_source_needs_the_previewed_count(
    committed_engine: Engine, corpus: Path
) -> None:
    imported(committed_engine, corpus)
    code, out = run(committed_engine, "remove", "--source", "lexflow-synthetic")
    assert "13 judgment(s)" in out and "--confirm 13" in out
    with pytest.raises(cli.CommandError, match="does not match"):
        run(committed_engine, "remove", "--source", "lexflow-synthetic", "--confirm", "2")
    code, out = run(committed_engine, "remove", "--source", "lexflow-synthetic", "--confirm", "13")
    assert code == 0 and count(committed_engine, Judgment) == 0
    assert count(committed_engine, JudgmentChunk) == 0  # text removed with them
    with Session(committed_engine) as session:
        event = session.scalars(
            select(AuditEvent).where(AuditEvent.action == "judgment.removed")
        ).one()
    assert event.details == {"source": "lexflow-synthetic", "judgments": 13}
    with pytest.raises(cli.CommandError, match="No source"):
        run(committed_engine, "remove", "--source", "nothing-here")


def test_uuid_namespace_is_fixed() -> None:
    assert uuid.UUID("6f0b2d3e-9a8c-5b1e-8f4a-3c2d1e0f9a7b") == importer.JUDGMENT_NAMESPACE
