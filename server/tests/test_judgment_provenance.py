"""Judgment provenance and import runs (Batch 2, manifest format 2).

Uses the SYNTHETIC judgment fixtures, turned into a format-2 manifest with
invented provenance values; no genuine judgment is involved. The rules for
real sources are checked by validation only (nothing is imported).
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from lexflow.extraction import Extracted, Limits, extract
from lexflow.models import Judgment, JudgmentImportRun, JudgmentProvenance
from lexflow.services import judgment_import as importer

FIXTURES = Path(__file__).parent / "fixtures" / "judgments" / "synthetic"
NOW = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
LIMITS = Limits(max_pages=100, max_text_bytes=1_000_000, max_unpacked_bytes=10_000_000)


def in_process(content_type: str, data: bytes, limits: Limits, timeout: float) -> Extracted:
    return extract(content_type, data, limits)


def v2(tmp_path: Path, **source_extra: Any) -> tuple[Path, dict[str, Any]]:
    target = tmp_path / "corpus"
    shutil.copytree(FIXTURES, target)
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    manifest["format"] = importer.FORMAT_V2
    manifest["source"].update(
        {
            "licence": "Invented for tests (SYNTHETIC); no licence applies.",
            "attribution": "SYNTHETIC test judgments - not real law.",
            **source_extra,
        }
    )
    manifest["dataset"] = {
        "name": "LexFlow synthetic fixtures",
        "publisher": "LexFlow developers",
        "url": "https://fixtures.lexflow.invalid/synthetic",
        "version": "fixtures-v1",
        "retrieved_on": "2026-10-25",
    }
    for n, entry in enumerate(manifest["judgments"], start=1):
        entry["neutral_citation"] = f"SYN-NC-{n:03d}"
        entry["provenance"] = {"record_path": f"synthetic/{entry['id']}", "cnr": None}
    path = target / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path, manifest


def import_all(engine: Engine, path: Path) -> importer.Outcome:
    with Session(engine, expire_on_commit=False) as session:
        plan = importer.plan_import(session, path, max_bytes=10_000_000)
        return importer.apply_import(
            session,
            plan,
            update=False,
            limits=LIMITS,
            timeout_seconds=30,
            extract=in_process,
            operator="test",
            now=NOW,
        )


def test_format_2_stores_provenance_beside_each_judgment(
    committed_engine: Engine, tmp_path: Path
) -> None:
    path, manifest = v2(tmp_path)
    outcome = import_all(committed_engine, path)
    assert outcome.imported and not outcome.rejected
    with Session(committed_engine) as session:
        rows = session.scalars(select(JudgmentProvenance)).all()
        assert len(rows) == len(outcome.imported)
        first = session.get(
            JudgmentProvenance,
            importer.judgment_id(manifest["source"]["key"], manifest["judgments"][0]["id"]),
        )
        assert first is not None
        assert first.neutral_citation == "SYN-NC-001"
        assert first.attribution == "SYNTHETIC test judgments - not real law."
        assert first.dataset is not None and first.dataset["version"] == "fixtures-v1"
        # Unknown values are left out, and the file's own hash is recorded.
        assert "cnr" not in first.source_record
        assert first.source_record["record_path"] == "synthetic/syn-001"
        judgment = session.get(Judgment, first.judgment_id)
        assert judgment is not None
        assert first.source_record["file_sha256"] == judgment.content_sha256


def test_each_run_is_recorded_with_what_was_not_imported(
    committed_engine: Engine, tmp_path: Path
) -> None:
    path, manifest = v2(tmp_path)
    first = import_all(committed_engine, path)
    # A second run of the same manifest: everything is unchanged, nothing duplicated.
    second = import_all(committed_engine, path)
    assert second.imported == [] and second.updated == []
    with Session(committed_engine) as session:
        runs = session.scalars(select(JudgmentImportRun).order_by(JudgmentImportRun.id)).all()
        assert len(runs) == 2
        by_id = {r.id: r for r in runs}
        one, two = by_id[first.run_id], by_id[second.run_id]  # type: ignore[index]
        assert one.counts["imported"] == len(first.imported)
        assert (
            two.counts["planned"]["unchanged"]
            == len(manifest["judgments"])
            - one.counts["planned"]["invalid"]
            - one.counts["planned"]["duplicate"]
        )
        assert two.manifest_format == importer.FORMAT_V2
        assert session.scalar(select(func.count()).select_from(Judgment)) == len(first.imported)


def test_an_invalid_item_is_recorded_with_its_reason(
    committed_engine: Engine, tmp_path: Path
) -> None:
    path, manifest = v2(tmp_path)
    manifest["judgments"][0]["file"] = "missing.pdf"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    outcome = import_all(committed_engine, path)
    with Session(committed_engine) as session:
        run = session.get(JudgmentImportRun, outcome.run_id)
        assert run is not None
        assert {"id": manifest["judgments"][0]["id"], "status": "invalid",
                "reason": "the file does not exist"} in run.items  # fmt: skip


def test_format_1_cannot_carry_format_2_fields() -> None:
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    manifest["source"]["attribution"] = "x"
    with pytest.raises(ValueError, match="need format 'lexflow-judgments/2'"):
        importer.Manifest.model_validate(manifest)


def test_a_real_source_must_say_what_attribution_to_show() -> None:
    manifest: dict[str, Any] = {
        "format": importer.FORMAT_V2,
        "source": {
            "key": "example-official-portal",
            "name": "Example official portal",
            "terms_url": "https://court.example.org/copyright",
            "terms_checked_on": "2026-10-25",
            "terms_checked_by": "A. Reviewer",
            "permitted_use": "Reproduction with acknowledgement (as recorded).",
        },
        "judgments": [
            {
                "id": "x-1",
                "title": "A v. B",
                "court": "Example Court",
                "source_url": "https://court.example.org/x-1",
                "file": "x.pdf",
            }
        ],
    }
    with pytest.raises(ValueError, match="needs the attribution"):
        importer.Manifest.model_validate(manifest)
    manifest["source"]["attribution"] = "Source: Example official portal."
    assert importer.Manifest.model_validate(manifest).source.attribution


@pytest.mark.parametrize(
    "provenance",
    [{"Bad Key": "x"}, {"cnr": ""}, {f"k{i}": "v" for i in range(31)}],
)
def test_provenance_fields_are_bounded(provenance: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        importer.JudgmentIn.model_validate(
            {
                "id": "x",
                "title": "t",
                "court": "c",
                "source_url": "https://x.invalid/x",
                "file": "x.pdf",
                "provenance": provenance,
            }
        )
