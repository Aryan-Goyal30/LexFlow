"""Importing judgments from a local folder described by a manifest (Phase 4).

LexFlow never crawls or downloads judgments. An operator places the files in a
folder with a ``manifest.json``::

    {
      "format": "lexflow-judgments/1",
      "source": {
        "key": "example-court-portal",
        "name": "Example Court Portal",
        "terms_url": "https://…/terms",
        "terms_checked_on": "2026-10-20",
        "terms_checked_by": "A. Advocate",
        "permitted_use": "What the terms allow, in the reader's words.",
        "synthetic": false
      },
      "judgments": [
        {"id": "the source's own identifier", "title": "…", "court": "…",
         "source_url": "https://…", "file": "files/x.pdf",
         "citation": "…", "decision_date": "2019-04-02", "year": 2019,
         "bench": "…", "practice_areas": ["…"]}
      ]
    }

``citation``, ``decision_date``, ``year``, ``bench`` and ``practice_areas``
are optional; nothing is guessed when they are missing.

Format ``lexflow-judgments/2`` (Batch 2) adds provenance for genuine
judgments: on the source, a ``licence`` statement and the ``attribution`` to
show (required for a real source); a ``dataset`` block (name, publisher,
https URL, version or snapshot, date retrieved); and per judgment a
``neutral_citation`` and a ``provenance`` map of the source's own record
fields (for example ``cnr``, ``case_id``, ``record_path``, ``scraped_at``,
``original_sha256``). They are stored in ``judgment_provenance`` (migration
0014), separate from the judgment text; each run is recorded in
``judgment_import_runs`` with every item that was not imported and why. Every judgment needs
its source and a source URL; every source needs a terms-of-use record (who
read which terms, when, and what they permit). Synthetic (invented) sources
must use reserved ``.invalid`` web addresses and are refused outside test
databases.

The ``plan`` changes nothing. ``apply`` extracts each file's text with the
Phase 3 extractors (in a child process, with the same limits) and stores each
judgment, its page-aware text and chunks in its own transaction, so a failure
never leaves a half-imported judgment.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from lexflow.extraction import DOCX, PDF, TXT, Extracted, ExtractionError, Limits
from lexflow.extraction.chunking import chunk_sections
from lexflow.models import (
    Judgment,
    JudgmentChunk,
    JudgmentImportRun,
    JudgmentProvenance,
    JudgmentSection,
    JudgmentSource,
)

# Fixed namespace: a judgment's id is uuid5(source key / source's own id), so
# importing it again (or into another database) gives the same id.
JUDGMENT_NAMESPACE = uuid.UUID("6f0b2d3e-9a8c-5b1e-8f4a-3c2d1e0f9a7b")
FORMAT = "lexflow-judgments/1"
FORMAT_V2 = "lexflow-judgments/2"
PROVENANCE_KEY = re.compile(r"[a-z][a-z0-9_]{0,39}")
PROVENANCE_MAX = 30
CONTENT_TYPES = {".pdf": PDF, ".docx": DOCX, ".txt": TXT}
RESERVED_SUFFIXES = (".invalid", ".test", ".example", ".localhost")
MAX_JUDGMENTS = 5000

ExtractFn = Callable[[str, bytes, Limits, float], Extracted]


class ManifestError(Exception):
    """The manifest cannot be used at all (nothing is imported)."""


def judgment_id(source_key: str, source_document_id: str) -> uuid.UUID:
    return uuid.uuid5(JUDGMENT_NAMESPACE, f"{source_key}/{source_document_id}")


def _https_url(value: str, *, synthetic: bool | None = None) -> str:
    value = value.strip()
    parts = urlsplit(value)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username
        or parts.password
        or len(value) > 2000
        or any(c.isspace() for c in value)
    ):
        raise ValueError("must be an https:// address without spaces or credentials")
    host = parts.hostname.lower()
    if synthetic is True and not host.endswith(".invalid"):
        raise ValueError("a synthetic source must use reserved .invalid addresses")
    if synthetic is False and (host == "localhost" or host.endswith(RESERVED_SUFFIXES)):
        raise ValueError("a reserved test address cannot belong to a real source")
    return value


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SourceIn(_Strict):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    name: str = Field(min_length=1, max_length=200)
    terms_url: str
    terms_checked_on: date
    terms_checked_by: str = Field(min_length=1, max_length=200)
    permitted_use: str = Field(min_length=1, max_length=2000)
    synthetic: bool = False
    # Format 2 only: the licence as stated by the source, and what must be shown.
    licence: str | None = Field(default=None, min_length=1, max_length=500)
    attribution: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def _urls(self) -> SourceIn:
        self.terms_url = _https_url(self.terms_url, synthetic=self.synthetic)
        return self


class DatasetIn(_Strict):
    """The dataset or snapshot the files were taken from (format 2)."""

    name: str = Field(min_length=1, max_length=200)
    publisher: str = Field(min_length=1, max_length=200)
    url: str
    version: str | None = Field(default=None, min_length=1, max_length=100)
    retrieved_on: date


class JudgmentIn(_Strict):
    id: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
    title: str = Field(min_length=1, max_length=500)
    court: str = Field(min_length=1, max_length=200)
    source_url: str
    file: str = Field(min_length=1, max_length=500)
    citation: str | None = Field(default=None, min_length=1, max_length=200)
    decision_date: date | None = None
    year: int | None = Field(default=None, ge=1800, le=2100)
    bench: str | None = Field(default=None, min_length=1, max_length=300)
    practice_areas: list[str] = Field(default_factory=list, max_length=20)
    # Format 2 only.
    neutral_citation: str | None = Field(default=None, min_length=1, max_length=100)
    provenance: dict[str, str | int | None] = Field(default_factory=dict)

    @field_validator("provenance")
    @classmethod
    def _provenance(cls, value: dict[str, str | int | None]) -> dict[str, str | int | None]:
        if len(value) > PROVENANCE_MAX:
            raise ValueError(f"at most {PROVENANCE_MAX} provenance fields")
        for key, item in value.items():
            if not PROVENANCE_KEY.fullmatch(key):
                raise ValueError(f"provenance key {key!r} must be lower_snake_case")
            if isinstance(item, str) and not 1 <= len(item) <= 500:
                raise ValueError(f"provenance value of {key!r} needs 1 to 500 characters")
        # Unknown values are left out, never stored as guesses.
        return {k: v for k, v in value.items() if v is not None}

    @field_validator("practice_areas")
    @classmethod
    def _areas(cls, value: list[str]) -> list[str]:
        cleaned = [v.strip() for v in value]
        if any(not v or len(v) > 100 for v in cleaned):
            raise ValueError("each practice area needs 1 to 100 characters")
        return sorted(set(cleaned))

    @model_validator(mode="after")
    def _year(self) -> JudgmentIn:
        if self.decision_date is not None:
            if self.year is not None and self.year != self.decision_date.year:
                raise ValueError("year does not match decision_date")
            self.year = self.decision_date.year
        return self


class Manifest(_Strict):
    format: Literal["lexflow-judgments/1", "lexflow-judgments/2"]
    source: SourceIn
    dataset: DatasetIn | None = None
    judgments: list[JudgmentIn] = Field(min_length=1, max_length=MAX_JUDGMENTS)

    @model_validator(mode="after")
    def _entries(self) -> Manifest:
        if self.format == FORMAT:
            v2_fields = (
                self.source.licence is not None
                or self.source.attribution is not None
                or self.dataset is not None
                or any(e.neutral_citation or e.provenance for e in self.judgments)
            )
            if v2_fields:
                raise ValueError(
                    "licence, attribution, dataset, neutral_citation and provenance need "
                    f"format {FORMAT_V2!r}"
                )
        elif not self.source.synthetic and self.source.attribution is None:
            raise ValueError("a real source needs the attribution to show with its judgments")
        if self.dataset is not None:
            self.dataset.url = _https_url(self.dataset.url, synthetic=self.source.synthetic)
        seen: set[str] = set()
        for entry in self.judgments:
            if entry.id in seen:
                raise ValueError(f"judgment id {entry.id!r} appears twice")
            seen.add(entry.id)
            entry.source_url = _https_url(entry.source_url, synthetic=self.source.synthetic)
        return self


Status = Literal["new", "unchanged", "changed", "duplicate", "invalid"]


@dataclass
class PlanItem:
    entry: JudgmentIn
    id: uuid.UUID
    status: Status
    reason: str = ""
    path: Path | None = None
    sha256: str = ""
    size: int = 0


@dataclass
class Plan:
    manifest: Manifest
    manifest_sha256: str
    folder: Path
    items: list[PlanItem] = field(default_factory=list)
    source_change: str = ""  # "", "new" or "terms record updated"

    def count(self, *statuses: Status) -> int:
        return sum(1 for item in self.items if item.status in statuses)


def load_manifest(path: Path) -> tuple[Manifest, str]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ManifestError(f"Cannot read {path.name}: {exc.strerror}.") from exc
    try:
        manifest = Manifest.model_validate(json.loads(raw.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"{path.name} is not valid UTF-8 JSON: {exc}.") from exc
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in error['loc'])}: {error['msg']}"
            for error in exc.errors()[:10]
        )
        raise ManifestError(f"{path.name} is not a valid manifest: {problems}") from exc
    return manifest, hashlib.sha256(raw).hexdigest()


def _file(folder: Path, relative: str, max_bytes: int) -> tuple[Path | None, str]:
    candidate = (folder / relative).resolve()
    if not candidate.is_relative_to(folder):
        return None, "the file path leaves the manifest's folder"
    suffix = candidate.suffix.lower()
    if suffix not in CONTENT_TYPES:
        return None, "only .pdf, .docx and .txt files can be imported"
    if not candidate.is_file():
        return None, "the file does not exist"
    if candidate.stat().st_size == 0 or candidate.stat().st_size > max_bytes:
        return None, "the file is empty or larger than the upload limit"
    return candidate, ""


def plan_import(session: Session, manifest_path: Path, *, max_bytes: int) -> Plan:
    """What an import would do, judgment by judgment. Changes nothing."""
    manifest, manifest_sha = load_manifest(manifest_path)
    folder = manifest_path.resolve().parent
    plan = Plan(manifest, manifest_sha, folder)
    source = session.scalar(select(JudgmentSource).where(JudgmentSource.key == manifest.source.key))
    if source is None:
        plan.source_change = "new"
    else:
        if source.is_synthetic != manifest.source.synthetic:
            raise ManifestError(
                f"Source {source.key!r} is recorded as "
                f"{'synthetic' if source.is_synthetic else 'real'}; the manifest says otherwise."
            )
        recorded = (
            source.name,
            source.terms_url,
            source.terms_checked_on,
            source.terms_checked_by,
            source.permitted_use,
        )
        incoming = manifest.source
        if recorded != (
            incoming.name,
            incoming.terms_url,
            incoming.terms_checked_on,
            incoming.terms_checked_by,
            incoming.permitted_use,
        ):
            plan.source_change = "terms record updated"

    seen_hashes: dict[str, str] = {}
    for entry in manifest.judgments:
        item = PlanItem(entry, judgment_id(manifest.source.key, entry.id), "new")
        plan.items.append(item)
        path, problem = _file(folder, entry.file, max_bytes)
        if path is None:
            item.status, item.reason = "invalid", problem
            continue
        data = path.read_bytes()
        item.path, item.size, item.sha256 = path, len(data), hashlib.sha256(data).hexdigest()
        if item.sha256 in seen_hashes:
            item.status = "duplicate"
            item.reason = f"same file as {seen_hashes[item.sha256]!r} in this manifest"
            continue
        seen_hashes[item.sha256] = entry.id
        existing = session.get(Judgment, item.id)
        same_content = session.scalar(
            select(Judgment.id).where(Judgment.content_sha256 == item.sha256)
        )
        if existing is not None:
            item.status = "unchanged" if existing.content_sha256 == item.sha256 else "changed"
            if item.status == "changed" and same_content is not None:
                item.status, item.reason = "duplicate", "this file is already another judgment"
        elif same_content is not None:
            item.status, item.reason = "duplicate", "this file is already in the collection"
        if item.status in ("new", "changed") and entry.citation:
            other = session.scalar(
                select(Judgment.id).where(
                    func.lower(Judgment.citation) == entry.citation.lower(),
                    Judgment.id != item.id,
                )
            )
            if other is not None:
                item.status, item.reason = "duplicate", "another judgment has this citation"
    return plan


@dataclass(frozen=True)
class Outcome:
    imported: list[uuid.UUID]
    updated: list[uuid.UUID]
    rejected: list[tuple[str, str]]  # (manifest id, reason)
    run_id: uuid.UUID | None = None  # the judgment_import_runs row, from migration 0014


def provenance_tables(session: Session) -> bool:
    """False before migration 0014: provenance and run records are then skipped."""
    return session.scalar(text("SELECT to_regclass('judgment_import_runs')")) is not None


def _source(session: Session, incoming: SourceIn) -> JudgmentSource:
    source = session.scalar(select(JudgmentSource).where(JudgmentSource.key == incoming.key))
    if source is None:
        source = JudgmentSource(key=incoming.key, is_synthetic=incoming.synthetic)
        session.add(source)
    source.name = incoming.name
    source.terms_url = incoming.terms_url
    source.terms_checked_on = incoming.terms_checked_on
    source.terms_checked_by = incoming.terms_checked_by
    source.permitted_use = incoming.permitted_use
    session.flush()
    return source


def apply_import(
    session: Session,
    plan: Plan,
    *,
    update: bool,
    limits: Limits,
    timeout_seconds: float,
    extract: ExtractFn,
    operator: str,
    now: datetime,
) -> Outcome:
    """Import the plan's new judgments (and changed ones with ``update``)."""
    started = now
    with_provenance = provenance_tables(session)
    source = _source(session, plan.manifest.source)
    source_id = source.id
    session.commit()
    imported: list[uuid.UUID] = []
    updated: list[uuid.UUID] = []
    rejected: list[tuple[str, str]] = []
    for item in plan.items:
        if item.status not in ("new", "changed") or (item.status == "changed" and not update):
            continue
        assert item.path is not None  # noqa: S101 - set for new/changed items
        entry = item.entry
        data = item.path.read_bytes()
        if hashlib.sha256(data).hexdigest() != item.sha256:
            rejected.append((entry.id, "the file changed since the preview"))
            continue
        content_type = CONTENT_TYPES[item.path.suffix.lower()]
        try:
            extracted = extract(content_type, data, limits, timeout_seconds)
        except ExtractionError as exc:
            rejected.append((entry.id, f"{exc.code}: {exc.message}"))
            continue
        sections = extracted.sections
        chunks = chunk_sections(sections, 1200, 200)
        if not any(s.text.strip() for s in sections):
            rejected.append((entry.id, "no text was found in the file"))
            continue
        try:
            judgment = session.get(Judgment, item.id)
            if judgment is None:
                judgment = Judgment(id=item.id, source_id=source_id, source_document_id=entry.id)
                session.add(judgment)
            else:
                session.execute(
                    delete(JudgmentSection).where(JudgmentSection.judgment_id == item.id)
                )
            judgment.source_url = entry.source_url
            judgment.title = entry.title
            judgment.court = entry.court
            judgment.citation = entry.citation
            judgment.decision_date = entry.decision_date
            judgment.year = entry.year
            judgment.bench = entry.bench
            judgment.practice_areas = entry.practice_areas
            judgment.content_type = content_type
            judgment.content_sha256 = item.sha256
            judgment.size_bytes = item.size
            judgment.extractor = extracted.extractor
            judgment.page_count = extracted.page_count
            judgment.section_count = len(sections)
            judgment.char_count = sum(len(s.text) for s in sections)
            judgment.chunk_count = len(chunks)
            judgment.imported_at = now
            judgment.imported_by = operator
            judgment.manifest_sha256 = plan.manifest_sha256
            judgment.index_status = "disabled"
            judgment.embedding_model = None
            judgment.indexed_at = None
            session.flush()
            session.add_all(
                JudgmentSection(
                    judgment_id=item.id, number=n, page_number=s.page_number, text=s.text
                )
                for n, s in enumerate(sections, start=1)
            )
            session.flush()
            if with_provenance:
                _provenance(session, plan.manifest, entry, item, now)
            session.add_all(
                JudgmentChunk(
                    judgment_id=item.id,
                    number=c.number,
                    section_number=c.section_number,
                    page_number=c.page_number,
                    char_start=c.char_start,
                    char_end=c.char_end,
                    text=c.text,
                    content_sha256=c.content_sha256,
                )
                for c in chunks
            )
            session.commit()
        except IntegrityError:
            session.rollback()
            rejected.append((entry.id, "it conflicts with a judgment already stored"))
            continue
        (updated if item.status == "changed" else imported).append(item.id)
    run_id = (
        _record_run(session, plan, imported, updated, rejected, operator, started, now)
        if with_provenance
        else None
    )
    return Outcome(imported, updated, rejected, run_id)


def _provenance(
    session: Session, manifest: Manifest, entry: JudgmentIn, item: PlanItem, now: datetime
) -> None:
    record: dict[str, str | int | None] = dict(entry.provenance)
    record.setdefault("file_sha256", item.sha256)
    row = session.get(JudgmentProvenance, item.id)
    if row is None:
        row = JudgmentProvenance(judgment_id=item.id)
        session.add(row)
    row.neutral_citation = entry.neutral_citation
    row.source_record = record
    row.dataset = manifest.dataset.model_dump(mode="json") if manifest.dataset else None
    row.attribution = manifest.source.attribution
    row.recorded_at = now


def _record_run(
    session: Session,
    plan: Plan,
    imported: list[uuid.UUID],
    updated: list[uuid.UUID],
    rejected: list[tuple[str, str]],
    operator: str,
    started: datetime,
    finished: datetime,
) -> uuid.UUID:
    """The run's record: counts, and every item not imported with its reason."""
    statuses: list[Status] = ["new", "unchanged", "changed", "duplicate", "invalid"]
    items: list[dict[str, Any]] = [
        {"id": i.entry.id, "status": i.status, "reason": i.reason}
        for i in plan.items
        if i.status in ("duplicate", "invalid")
    ]
    items += [{"id": rid, "status": "rejected", "reason": reason} for rid, reason in rejected]
    run = JudgmentImportRun(
        source_key=plan.manifest.source.key,
        manifest_format=plan.manifest.format,
        manifest_sha256=plan.manifest_sha256,
        operator=operator,
        started_at=started,
        finished_at=finished,
        counts={
            "planned": {s: plan.count(s) for s in statuses},
            "imported": len(imported),
            "updated": len(updated),
            "rejected": len(rejected),
        },
        items=items,
    )
    session.add(run)
    session.commit()
    return run.id
