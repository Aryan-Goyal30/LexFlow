"""Turn a hand-picked folder of official judgment PDFs into an import manifest.

The owner (or a lawyer) downloads each judgment by hand from the official
portal, puts the PDFs in one folder, and fills ``selection.csv`` from the
portal's own record. This module checks that folder and writes a
``lexflow-judgments/2`` manifest for ``python -m lexflow.cli.judgments
import``. It makes no network request and never touches a database.

``selection.csv`` columns (header required; any other column is refused):

* required: ``file``, ``title``, ``court``, ``source_url``, ``selected_by``
* optional: ``decision_date`` (YYYY-MM-DD), ``year``, ``citation``,
  ``neutral_citation``, ``bench``, ``practice_areas`` (separated by ``;``),
  ``selection_reason``
* optional, how the file was obtained: ``retrieved_from`` (the exact official
  URL fetched), ``retrieved_at`` (ISO 8601, UTC), ``original_sha256`` (of the
  bytes as served) and ``original_transform`` (what was changed, if the
  imported file is not byte-identical to them; required in that case)
* optional, review and role: ``corpus_role`` (for example "core corpus" or
  "evaluation candidate"), ``legal_review`` (who reviewed it legally, and
  when, or that no legal review has been done) and ``notes`` (for example
  where editorial matter such as a headnote sits). Technical preparation
  (``selected_by``) is recorded apart from any legal review.

A blank cell means *unknown* and is left out of the manifest; nothing is
guessed or filled in. Every ``source_url`` must be on the profile's official
hosts. The id is the neutral citation when there is one (for example
``2023 INSC 123`` becomes ``nc-2023-INSC-123``), otherwise the first 16 hex
digits of the PDF's SHA-256 (``sha256-…``), so the same file always gets the
same id.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from lexflow.services import judgment_import as importer

CSV_NAME = "selection.csv"
REQUIRED = ("file", "title", "court", "source_url", "selected_by")
OPTIONAL = (
    "decision_date",
    "year",
    "citation",
    "neutral_citation",
    "bench",
    "practice_areas",
    "selection_reason",
    "retrieved_from",
    "retrieved_at",
    "original_sha256",
    "original_transform",
    "corpus_role",
    "legal_review",
    "notes",
)
SHA256 = re.compile(r"[0-9a-f]{64}")
RETRIEVED_AT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
MAX_ROWS = 500
MAX_CSV_BYTES = 1_000_000


@dataclass(frozen=True)
class Profile:
    """What is fixed for one source: its record, attribution and official hosts."""

    key: str
    name: str
    terms_url: str
    permitted_use: str
    licence: str
    attribution: str
    hosts: frozenset[str]
    synthetic: bool = False
    dataset: dict[str, str] | None = field(default=None)


# The e-SCR wording is quoted from the policy page saved on 2026-10-25 in
# docs/verification/batch2/source-evidence/scr-footer-cp.html. The attribution
# is the proposal in SOURCE_AND_LICENSING_REPORT.md section 5; the owner may
# replace it with --attribution.
E_SCR = Profile(
    key="sci-escr",
    name="Supreme Court of India - Supreme Court Reports (e-SCR)",
    terms_url="https://scr.sci.gov.in/scrsearch/?p=pdf_search/footerlinks/cp",
    permitted_use=(
        'Copyright policy: "The contents on this website shall not be reproduced '
        "partially or fully, without duly & prominently acknowledging the source. "
        "The contents of this website cannot be used in any misleading or "
        "objectionable context or derogatory manner. However the permission to "
        "reproduce the material available on the e-Courts website shall not extend "
        "to any material which is identified as being copyright of a third party. "
        "Authorization to reproduce such material must be obtained from the Courts "
        'Concerned." Terms: for reference purposes only; not a legal document. '
        "English versions only; regional and Hindi versions are excluded."
    ),
    licence="No licence stated; reproduction with prominent acknowledgement (copyright policy).",
    attribution=(
        "Source: Supreme Court of India, Supreme Court Reports (e-SCR), scr.sci.gov.in. "
        "Reproduced with acknowledgement under the portal's copyright policy. "
        "For reference only; not a legal document."
    ),
    hosts=frozenset({"scr.sci.gov.in", "www.sci.gov.in", "sci.gov.in"}),
)

# The Supreme Court's own website: judgment copies served from api.sci.gov.in
# (the current archive and the legacy JUDIS archive) and linked openly by the
# Court. The wording is quoted from the policy page saved on 2026-10-25 in
# docs/verification/batch2/source-evidence/sci-website-policies.html.
SCI_WEBSITE = Profile(
    key="sci-judgments",
    name="Supreme Court of India - judgments published on sci.gov.in",
    terms_url="https://www.sci.gov.in/website-policies/",
    permitted_use=(
        'Copyright policy: "The contents on this website shall not be reproduced '
        "partially or fully, without duly & prominently acknowledging the source. "
        "The contents of this website cannot be used in any misleading or "
        "objectionable context or derogatory manner. However, the permission to "
        "reproduce the material available on this website shall not extend to any "
        "material which is identified as being copyright of a third party. "
        "Authorization to reproduce such material must be obtained from the "
        'respective owner of the data." Terms and conditions: "The documents and '
        "information displayed in this website are for reference purposes only and "
        'the same do not constitute legal document." English judgment copies only.'
    ),
    licence="No licence stated; reproduction with prominent acknowledgement (copyright policy).",
    attribution=(
        "Source: Supreme Court of India, sci.gov.in (judgment copy as published by the "
        "Court). Reproduced with acknowledgement under the website's copyright policy. "
        "For reference only; not a legal document."
    ),
    hosts=frozenset({"api.sci.gov.in", "main.sci.gov.in", "www.sci.gov.in", "sci.gov.in"}),
)

PROFILES = {E_SCR.key: E_SCR, SCI_WEBSITE.key: SCI_WEBSITE}


class SelectionError(ValueError):
    """The folder cannot become a manifest; ``problems`` lists every reason."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


def _blank(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def entry_id(neutral_citation: str | None, sha256: str) -> str:
    if neutral_citation:
        slug = re.sub(r"[^A-Za-z0-9]+", "-", neutral_citation).strip("-")
        if slug:
            return f"nc-{slug}"
    return f"sha256-{sha256[:16]}"


def _official(url: str, profile: Profile) -> str | None:
    host = (urlsplit(url).hostname or "").lower()
    if host not in profile.hosts:
        return f"source_url host {host or '(none)'!r} is not an official host of {profile.key}"
    return None


def _retrieval(row: dict[str, str], sha: str, profile: Profile) -> dict[str, str | None] | str:
    """The retrieval columns, checked; a string is the problem found."""
    url = _blank(row.get("retrieved_from"))
    at = _blank(row.get("retrieved_at"))
    original = _blank(row.get("original_sha256"))
    transform = _blank(row.get("original_transform"))
    if url and (reason := _official(url, profile)):
        return reason.replace("source_url", "retrieved_from")
    if at and not RETRIEVED_AT.fullmatch(at):
        return "retrieved_at must look like 2026-10-25T09:30:00Z"
    if original and not SHA256.fullmatch(original):
        return "original_sha256 must be 64 lower-case hex digits"
    if original and original != sha and not transform:
        return "the file differs from original_sha256: original_transform must say how"
    if transform and not original:
        return "original_transform needs the original_sha256 it was applied to"
    return {
        "retrieved_from": url,
        "retrieved_at": at,
        "original_sha256": original,
        "original_transform": transform,
    }


def read_rows(folder: Path) -> list[dict[str, str]]:
    path = folder / CSV_NAME
    if not path.is_file():
        raise SelectionError([f"{CSV_NAME} is missing"])
    data = path.read_bytes()
    if len(data) > MAX_CSV_BYTES:
        raise SelectionError([f"{CSV_NAME} is larger than {MAX_CSV_BYTES} bytes"])
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    header = [h.strip() for h in reader.fieldnames or []]
    problems = [f"column {c!r} is missing" for c in REQUIRED if c not in header]
    problems += [f"column {c!r} is not recognised" for c in header if c not in REQUIRED + OPTIONAL]
    if problems:
        raise SelectionError(problems)
    rows = [{k.strip(): v for k, v in row.items() if k is not None} for row in reader]
    rows = [r for r in rows if any(_blank(v) for v in r.values())]
    if not rows:
        raise SelectionError([f"{CSV_NAME} has no rows"])
    if len(rows) > MAX_ROWS:
        raise SelectionError([f"{CSV_NAME} has more than {MAX_ROWS} rows"])
    return rows


def build_manifest(
    folder: Path,
    profile: Profile,
    *,
    checked_by: str,
    checked_on: date,
    attribution: str | None = None,
) -> dict[str, Any]:
    """The manifest for ``folder``, validated by the importer's own rules."""
    folder = folder.resolve()
    rows = read_rows(folder)
    problems: list[str] = []
    entries: list[dict[str, Any]] = []
    seen_ids: dict[str, int] = {}
    seen_sha: dict[str, int] = {}
    for line, row in enumerate(rows, start=2):
        where = f"row {line}"
        missing = [c for c in REQUIRED if not _blank(row.get(c))]
        if missing:
            problems.append(f"{where}: {', '.join(missing)} must not be blank")
            continue
        name = row["file"].strip()
        pdf = (folder / name).resolve()
        if pdf.parent != folder or not pdf.is_file():
            problems.append(f"{where}: {name!r} is not a file in the folder")
            continue
        data = pdf.read_bytes()
        if not data.startswith(b"%PDF-"):
            problems.append(f"{where}: {name!r} is not a PDF")
            continue
        sha = hashlib.sha256(data).hexdigest()
        if sha in seen_sha:
            problems.append(f"{where}: {name!r} is the same file as row {seen_sha[sha]}")
            continue
        seen_sha[sha] = line
        url = row["source_url"].strip()
        if reason := _official(url, profile):
            problems.append(f"{where}: {reason}")
            continue
        neutral = _blank(row.get("neutral_citation"))
        ident = entry_id(neutral, sha)
        if ident in seen_ids:
            problems.append(f"{where}: id {ident!r} repeats row {seen_ids[ident]}")
            continue
        seen_ids[ident] = line
        entry: dict[str, Any] = {
            "id": ident,
            "title": row["title"].strip(),
            "court": row["court"].strip(),
            "source_url": url,
            "file": name,
        }
        for column in ("citation", "decision_date", "bench"):
            if value := _blank(row.get(column)):
                entry[column] = value
        if year := _blank(row.get("year")):
            entry["year"] = int(year) if year.isdigit() else year
        if areas := _blank(row.get("practice_areas")):
            entry["practice_areas"] = [a.strip() for a in areas.split(";") if a.strip()]
        if neutral:
            entry["neutral_citation"] = neutral
        retrieval = _retrieval(row, sha, profile)
        if isinstance(retrieval, str):
            problems.append(f"{where}: {retrieval}")
            continue
        provenance = {
            "original_filename": name,
            "selected_by": row["selected_by"].strip(),
            "selection_reason": _blank(row.get("selection_reason")),
            **retrieval,
            "corpus_role": _blank(row.get("corpus_role")),
            "legal_review": _blank(row.get("legal_review")),
            "notes": _blank(row.get("notes")),
        }
        # Unknown values are left out of the manifest, never written as guesses.
        entry["provenance"] = {k: v for k, v in provenance.items() if v is not None}
        try:
            importer.JudgmentIn.model_validate(entry)
        except ValueError as error:
            problems.append(f"{where}: {_first_error(error)}")
            continue
        entries.append(entry)
    if problems:
        raise SelectionError(problems)
    manifest: dict[str, Any] = {
        "format": importer.FORMAT_V2,
        "source": {
            "key": profile.key,
            "name": profile.name,
            "terms_url": profile.terms_url,
            "terms_checked_on": checked_on.isoformat(),
            "terms_checked_by": checked_by,
            "permitted_use": profile.permitted_use,
            "synthetic": profile.synthetic,
            "licence": profile.licence,
            "attribution": attribution or profile.attribution,
        },
        "judgments": entries,
    }
    if profile.dataset is not None:
        manifest["dataset"] = profile.dataset
    try:
        importer.Manifest.model_validate(manifest)
    except ValueError as error:
        raise SelectionError([_first_error(error)]) from error
    return manifest


def _first_error(error: ValueError) -> str:
    errors = getattr(error, "errors", None)
    if callable(errors):
        first = errors()[0]
        place = ".".join(str(p) for p in first.get("loc", ()))
        return f"{place}: {first['msg']}" if place else str(first["msg"])
    return str(error)
