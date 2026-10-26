"""The hand-picked-folder adapter (Batch 2): selection.csv and PDFs to a manifest.

Every judgment here is INVENTED, and the profile uses reserved ``.invalid``
hosts, so nothing resembles a genuine record. The e-SCR profile is checked
only for its fixed values; no genuine judgment is read or imported.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from lexflow.extraction import Extracted, Limits, extract
from lexflow.models import JudgmentProvenance, JudgmentSource
from lexflow.services import judgment_import as importer
from lexflow.services import judgment_selection as selection
from tests.document_fixtures import pdf_with_pages

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "prepare_official_judgments.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lexflow_prepare_official", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


FAKE = selection.Profile(
    key="lexflow-synthetic-official",
    name="Invented official portal (SYNTHETIC)",
    terms_url="https://portal.lexflow.invalid/copyright",
    permitted_use="Invented terms for tests.",
    licence="None (SYNTHETIC).",
    attribution="SYNTHETIC: invented judgments for tests, not real law.",
    hosts=frozenset({"portal.lexflow.invalid"}),
    synthetic=True,
)
COLUMNS = ["file", "title", "court", "source_url", "selected_by", "neutral_citation",
           "decision_date", "citation", "practice_areas", "selection_reason"]  # fmt: skip


def folder_with(tmp_path: Path, rows: list[dict[str, str]], columns: list[str] = COLUMNS) -> Path:
    folder = tmp_path / "picked"
    folder.mkdir(exist_ok=True)
    for n, row in enumerate(rows):
        name = row.get("file", "")
        if name.endswith(".pdf") and not (folder / name).exists():
            text = f"SYNTHETIC judgment {n}. Passing off and prior use of the mark ZEPHRANT."
            (folder / name).write_bytes(pdf_with_pages([text]))
    with (folder / selection.CSV_NAME).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return folder


def row(n: int, **values: str) -> dict[str, str]:
    base = {
        "file": f"j{n}.pdf",
        "title": f"Invented Appellant {n} v. Invented Respondent (SYNTHETIC)",
        "court": "Invented Supreme Court",
        "source_url": f"https://portal.lexflow.invalid/j/{n}",
        "selected_by": "Test Reviewer",
        "neutral_citation": "",
        "decision_date": "",
        "citation": "",
        "practice_areas": "",
        "selection_reason": "",
    }
    return base | values


def build(folder: Path) -> dict[str, Any]:
    return selection.build_manifest(
        folder, FAKE, checked_by="Test Reviewer", checked_on=date(2026, 10, 25)
    )


def test_a_folder_becomes_a_format_2_manifest_with_unknowns_left_out(tmp_path: Path) -> None:
    folder = folder_with(
        tmp_path,
        [
            row(1, neutral_citation="2099 SYN 7", decision_date="2099-01-31",
                practice_areas="Trade marks; Passing off", selection_reason="prior use"),
            row(2),
        ],
    )  # fmt: skip
    manifest = build(folder)
    first, second = manifest["judgments"]
    assert manifest["format"] == importer.FORMAT_V2
    assert first["id"] == "nc-2099-SYN-7" and first["neutral_citation"] == "2099 SYN 7"
    assert first["practice_areas"] == ["Trade marks", "Passing off"]
    sha = hashlib.sha256((folder / "j2.pdf").read_bytes()).hexdigest()
    assert second["id"] == f"sha256-{sha[:16]}"
    # Blank cells are unknown: no key at all, never a guess.
    for key in ("decision_date", "citation", "neutral_citation", "year", "practice_areas"):
        assert key not in second
    assert second["provenance"] == {
        "original_filename": "j2.pdf",
        "selected_by": "Test Reviewer",
    }
    assert manifest["source"]["attribution"] == FAKE.attribution


@pytest.mark.parametrize(
    ("rows", "problem"),
    [
        ([row(1, source_url="https://elsewhere.lexflow.invalid/1")], "not an official host"),
        ([row(1, title="")], "title must not be blank"),
        ([row(1, file="../j1.pdf")], "is not a file in the folder"),
        ([row(1, file="absent.txt")], "is not a file in the folder"),
        ([row(1, decision_date="31/01/2099")], "decision_date"),
        ([row(1, neutral_citation="2099 SYN 7"), row(2, neutral_citation="2099 SYN 7")],
         "repeats row 2"),
    ],
)  # fmt: skip
def test_every_problem_is_reported_and_nothing_is_written(
    tmp_path: Path, rows: list[dict[str, str]], problem: str
) -> None:
    folder = folder_with(tmp_path, rows)
    with pytest.raises(selection.SelectionError, match=problem):
        build(folder)
    assert not (folder / "manifest.json").exists()


def test_a_non_pdf_and_a_repeated_file_are_refused(tmp_path: Path) -> None:
    folder = folder_with(tmp_path, [row(1), row(2, file="j1.pdf"), row(3, file="notes.pdf")])
    (folder / "notes.pdf").write_text("not a pdf", encoding="utf-8")
    with pytest.raises(selection.SelectionError) as caught:
        build(folder)
    assert caught.value.problems == [
        "row 3: 'j1.pdf' is the same file as row 2",
        "row 4: 'notes.pdf' is not a PDF",
    ]


def test_unknown_and_missing_columns_are_refused(tmp_path: Path) -> None:
    folder = folder_with(tmp_path, [{"file": "j1.pdf", "title": "t", "verdict": "x"}],
                         columns=["file", "title", "verdict"])  # fmt: skip
    with pytest.raises(selection.SelectionError) as caught:
        build(folder)
    assert "column 'court' is missing" in caught.value.problems
    assert "column 'verdict' is not recognised" in caught.value.problems


def test_the_e_scr_profile_is_a_real_source_on_official_hosts() -> None:
    profile = selection.PROFILES["sci-escr"]
    assert not profile.synthetic
    assert profile.terms_url == "https://scr.sci.gov.in/scrsearch/?p=pdf_search/footerlinks/cp"
    assert "prominently acknowledging the source" in profile.permitted_use
    assert profile.hosts <= {"scr.sci.gov.in", "www.sci.gov.in", "sci.gov.in"}
    # The real profile cannot be pointed at a reserved or unofficial address.
    assert selection._official("https://portal.lexflow.invalid/x", profile)


def test_the_script_writes_the_manifest_and_reports_problems(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setitem(selection.PROFILES, FAKE.key, FAKE)
    script = load_script()
    monkeypatch.setitem(script.PROFILES, FAKE.key, FAKE)
    folder = folder_with(tmp_path, [row(1)])
    argv = [str(folder), "--profile", FAKE.key, "--checked-by", "Test Reviewer"]
    assert script.main(argv) == 0
    assert (folder / "manifest.json").is_file()
    assert "never the live one" in capsys.readouterr().out
    folder_with(tmp_path, [row(1, title="")])
    assert script.main(argv) == 1
    assert "title must not be blank" in capsys.readouterr().err


def test_the_manifest_imports_with_its_provenance(committed_engine: Engine, tmp_path: Path) -> None:
    folder = folder_with(tmp_path, [row(1, neutral_citation="2099 SYN 7"), row(2)])
    path = folder / "manifest.json"
    path.write_text(json.dumps(build(folder)), encoding="utf-8")

    def in_process(content_type: str, data: bytes, limits: Limits, timeout: float) -> Extracted:
        return extract(content_type, data, limits)

    with Session(committed_engine, expire_on_commit=False) as session:
        plan = importer.plan_import(session, path, max_bytes=10_000_000)
        outcome = importer.apply_import(
            session, plan, update=False, extract=in_process, operator="test", timeout_seconds=30,
            limits=Limits(max_pages=10, max_text_bytes=100_000, max_unpacked_bytes=1_000_000),
            now=datetime(2026, 10, 25, tzinfo=UTC),
        )  # fmt: skip
    assert len(outcome.imported) == 2 and not outcome.rejected
    with Session(committed_engine) as session:
        source = session.scalars(select(JudgmentSource)).one()
        assert source.is_synthetic
        stored = session.get(JudgmentProvenance, importer.judgment_id(FAKE.key, "nc-2099-SYN-7"))
        assert stored is not None and stored.neutral_citation == "2099 SYN 7"
        assert stored.source_record["selected_by"] == "Test Reviewer"
        assert stored.attribution == FAKE.attribution


RETRIEVAL = [*COLUMNS, "retrieved_from", "retrieved_at", "original_sha256", "original_transform"]


def test_retrieval_details_are_kept_and_a_changed_file_must_say_how(tmp_path: Path) -> None:
    folder = folder_with(tmp_path, [row(1)], columns=RETRIEVAL)
    sha = hashlib.sha256((folder / "j1.pdf").read_bytes()).hexdigest()
    fetched = {
        "retrieved_from": "https://portal.lexflow.invalid/raw/1",
        "retrieved_at": "2026-10-25T09:30:00Z",
        "original_sha256": "a" * 64,
    }
    folder_with(tmp_path, [row(1, **fetched)], columns=RETRIEVAL)
    with pytest.raises(selection.SelectionError, match="original_transform must say how"):
        build(folder)
    stripped = fetched | {"original_transform": "removed a 4-byte length prefix (invented)"}
    folder_with(tmp_path, [row(1, **stripped)], columns=RETRIEVAL)
    provenance = build(folder)["judgments"][0]["provenance"]
    assert provenance["retrieved_from"] == "https://portal.lexflow.invalid/raw/1"
    assert provenance["original_sha256"] == "a" * 64
    assert provenance["original_transform"].startswith("removed a 4-byte")
    # Byte-identical to the original: no transformation to state.
    folder_with(tmp_path, [row(1, **(fetched | {"original_sha256": sha}))], columns=RETRIEVAL)
    assert "original_transform" not in build(folder)["judgments"][0]["provenance"]


@pytest.mark.parametrize(
    ("values", "problem"),
    [
        ({"retrieved_from": "https://elsewhere.lexflow.invalid/1"}, "retrieved_from host"),
        ({"retrieved_at": "25/10/2026"}, "retrieved_at must look like"),
        ({"original_sha256": "XYZ"}, "64 lower-case hex"),
        ({"original_transform": "something"}, "needs the original_sha256"),
    ],
)
def test_bad_retrieval_details_are_refused(
    tmp_path: Path, values: dict[str, str], problem: str
) -> None:
    folder = folder_with(tmp_path, [row(1, **values)], columns=RETRIEVAL)
    with pytest.raises(selection.SelectionError, match=problem):
        build(folder)


def test_the_sci_website_profile_quotes_its_own_policy() -> None:
    profile = selection.PROFILES["sci-judgments"]
    assert not profile.synthetic
    assert profile.terms_url == "https://www.sci.gov.in/website-policies/"
    assert "respective owner of the data" in profile.permitted_use
    assert "for reference purposes only" in profile.permitted_use
    assert "api.sci.gov.in" in profile.hosts
    assert selection._official("https://indiankanoon.org/doc/1/", profile)


def test_role_review_and_notes_are_recorded_apart_from_the_technical_selection(
    tmp_path: Path,
) -> None:
    columns = [*COLUMNS, "corpus_role", "legal_review", "notes"]
    values = {
        "corpus_role": "evaluation candidate",
        "legal_review": "not performed",
        "notes": "invented headnote on page 1 (SYNTHETIC)",
    }
    folder = folder_with(tmp_path, [row(1, **values), row(2)], columns=columns)
    first, second = build(folder)["judgments"]
    assert first["provenance"]["legal_review"] == "not performed"
    assert first["provenance"]["selected_by"] == "Test Reviewer"
    assert first["provenance"]["corpus_role"] == "evaluation candidate"
    assert "notes" not in second["provenance"] and "legal_review" not in second["provenance"]
    folder_with(tmp_path, [row(1, notes="x" * 501)], columns=columns)
    with pytest.raises(selection.SelectionError, match="1 to 500 characters"):
        build(folder)
