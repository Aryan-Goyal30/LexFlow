"""Validating uploaded files.

The browser's filename extension and Content-Type are only claims. Every upload
is checked against the file's actual leading bytes (and, for DOCX, its ZIP
directory; for text, strict UTF-8 without NUL bytes). The stored content type
comes from this check, never from the client.
"""

from __future__ import annotations

import codecs
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from lexflow.domain import DOCUMENT_NAME_MAX


@dataclass(frozen=True)
class FileKind:
    content_type: str
    label: str  # shown in the document list, matches the front end's labels
    inline: bool  # safe to display in the browser rather than download


KINDS: dict[str, FileKind] = {
    ".pdf": FileKind("application/pdf", "PDF", inline=True),
    ".doc": FileKind("application/msword", "Word document", inline=False),
    ".docx": FileKind(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "Word document",
        inline=False,
    ),
    ".txt": FileKind("text/plain", "Text", inline=True),
    ".png": FileKind("image/png", "Image", inline=True),
    ".jpg": FileKind("image/jpeg", "Image", inline=True),
    ".jpeg": FileKind("image/jpeg", "Image", inline=True),
    ".gif": FileKind("image/gif", "Image", inline=True),
    ".webp": FileKind("image/webp", "Image", inline=True),
}

ACCEPTED_LABEL = "PDF, Word, text or image (PNG, JPG, GIF, WebP)"
HEAD_BYTES = 16
OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def clean_filename(raw: str | None) -> str:
    """The display name to store: last path component, no control characters.

    Returns "" when nothing usable remains. The result is only ever used as a
    label and in database rows, never as a filesystem path.
    """
    # Browsers escape these three characters in multipart filenames (WHATWG
    # HTML spec); nothing else is decoded, so a literal "%41" stays as typed.
    name = (raw or "").replace("%22", '"').replace("%0D", "\r").replace("%0A", "\n")
    name = name.replace("\\", "/")
    name = PurePosixPath(name).name
    name = unicodedata.normalize("NFC", name)
    # Drop control and format characters (including bidi overrides like U+202E).
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C").strip()
    if name in {".", ".."}:
        return ""
    if len(name) > DOCUMENT_NAME_MAX:
        suffix = PurePosixPath(name).suffix[:16]
        name = name[: DOCUMENT_NAME_MAX - len(suffix)] + suffix
    return name


def kind_for(name: str) -> FileKind | None:
    suffix = PurePosixPath(name).suffix.lower()
    stem = name[: -len(suffix)] if suffix else name
    if not stem.strip():  # e.g. ".pdf"
        return None
    return KINDS.get(suffix)


class TextCheck:
    """Incremental check that a stream is UTF-8 text without NUL bytes."""

    def __init__(self) -> None:
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="strict")
        self.ok = True

    def feed(self, chunk: bytes, final: bool = False) -> None:
        if not self.ok:
            return
        if b"\x00" in chunk:
            self.ok = False
            return
        try:
            self._decoder.decode(chunk, final)
        except UnicodeDecodeError:
            self.ok = False


def _is_docx(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())  # reads the directory only, no extraction
    except (zipfile.BadZipFile, OSError):
        return False
    return "[Content_Types].xml" in names and any(n.startswith("word/") for n in names)


def content_matches(kind: FileKind, head: bytes, path: Path, text_ok: bool) -> bool:
    """Whether the stored bytes really are the kind the extension claims."""
    match kind.content_type:
        case "application/pdf":
            return head.startswith(b"%PDF-")
        case "image/png":
            return head.startswith(b"\x89PNG\r\n\x1a\n")
        case "image/jpeg":
            return head.startswith(b"\xff\xd8\xff")
        case "image/gif":
            return head[:6] in (b"GIF87a", b"GIF89a")
        case "image/webp":
            return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
        case "application/msword":
            return head.startswith(OLE_SIGNATURE)
        case "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return head.startswith(b"PK\x03\x04") and _is_docx(path)
        case "text/plain":
            return text_ok
    return False
