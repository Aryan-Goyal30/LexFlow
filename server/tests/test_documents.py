"""Document upload, listing, download and deletion."""

from __future__ import annotations

import asyncio
import hashlib
import io
import struct
import uuid
import zipfile
import zlib
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.types import Message

from lexflow.clock import get_today
from lexflow.models import Document
from lexflow.seed import sample_uuid
from lexflow.seed.loader import load_sample_data
from lexflow.services import documents as documents_service
from lexflow.services.uploads import clean_filename
from lexflow.storage import LocalDiskStorage, get_storage
from lexflow.upload_limit import MULTIPART_OVERHEAD

TODAY = date(2026, 10, 14)
CASE = str(sample_uuid("case", "case-1005"))
UPLOAD = f"/api/cases/{CASE}/documents"


# --- minimal real files of each supported format ----------------------------------


def png_bytes() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    pixels = zlib.compress(b"\x00\xff\x00\x00")
    return (
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", pixels) + chunk(b"IEND", b"")
    )


def _entry(name: str) -> zipfile.ZipInfo:
    # A fixed timestamp: otherwise each call stamps the current time and two
    # calls a second apart give different bytes (an intermittent failure).
    return zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))


def docx_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(_entry("[Content_Types].xml"), "<Types/>")
        archive.writestr(_entry("word/document.xml"), "<w:document/>")
    return buffer.getvalue()


def plain_zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(_entry("readme.txt"), "not a word document")
    return buffer.getvalue()


PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
SAMPLES: dict[str, bytes] = {
    "Rejoinder.pdf": PDF,
    "Exhibit.png": png_bytes(),
    "Photo.jpg": b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01" + b"\x00" * 32,
    "Scan.jpeg": b"\xff\xd8\xff\xdb" + b"\x00" * 32,
    "Animation.gif": b"GIF89a\x01\x00\x01\x00\x00\x00\x00;",
    "Picture.webp": b"RIFF\x1a\x00\x00\x00WEBPVP8 " + b"\x00" * 16,
    "Legacy.doc": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64,
    "Reply.docx": docx_bytes(),
    "Notes.txt": "Hearing notes – ₹ 3.85 crore, ünicode is fine.\n".encode(),
}


# --- fixtures -------------------------------------------------------------------------


@pytest.fixture
def storage_root(tmp_path: Path) -> Path:
    return tmp_path / "uploads"


@pytest.fixture
def seeded(db: Session, app: FastAPI, storage_root: Path) -> Session:
    load_sample_data(db)
    # Committed (into the test's outer transaction, still discarded afterwards),
    # so a rollback inside a request only undoes that request, as in production.
    db.commit()
    app.dependency_overrides[get_today] = lambda: TODAY
    app.dependency_overrides[get_storage] = lambda: LocalDiskStorage(storage_root)
    return db


def stored_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file() and ".staging" not in p.parts]


def staging_files(root: Path) -> list[Path]:
    staging = root / ".staging"
    return list(staging.iterdir()) if staging.exists() else []


def upload(client: TestClient, name: str, content: bytes, ctype: str = "application/pdf") -> Any:
    return client.post(UPLOAD, files={"file": (name, content, ctype)})


def multipart(boundary: str, filename: str, content: bytes) -> bytes:
    head = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{filename}"\r\nContent-Type: application/pdf\r\n\r\n'
    ).encode()
    return head + content + f"\r\n--{boundary}--\r\n".encode()


class AsgiRequest:
    """An upload sent straight to the ASGI app, recording how much body it reads.

    The HTTP test client reads the whole body before the app sees it; calling
    the app directly shows whether the server stops reading early.
    """

    def __init__(
        self,
        path: str,
        boundary: str,
        chunks: list[bytes],
        content_length: int | None = None,
        session: str | None = None,
    ) -> None:
        self.path = path
        self.chunks = chunks
        self.headers = [
            (b"host", b"testserver"),
            (b"x-lexflow-request", b"1"),
            (b"content-type", f"multipart/form-data; boundary={boundary}".encode()),
        ]
        if content_length is not None:
            self.headers.append((b"content-length", str(content_length).encode()))
        if session is not None:
            # As a browser sends it: the session cookie together with the app's origin.
            self.headers.append((b"cookie", f"lexflow_session={session}".encode()))
            self.headers.append((b"origin", b"http://localhost:5173"))
        self.body_reads = 0
        self.bytes_read = 0
        self.status: int | None = None

    async def receive(self) -> Message:
        if self.body_reads >= len(self.chunks):
            return {"type": "http.disconnect"}
        chunk = self.chunks[self.body_reads]
        self.body_reads += 1
        self.bytes_read += len(chunk)
        more = self.body_reads < len(self.chunks)
        return {"type": "http.request", "body": chunk, "more_body": more}

    async def send(self, message: Message) -> None:
        if message["type"] == "http.response.start" and self.status is None:
            self.status = message["status"]

    def send_to(self, app: FastAPI) -> int | None:
        scope: dict[str, Any] = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": self.path,
            "raw_path": self.path.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": self.headers,
            "client": ("127.0.0.1", 50000),
            "server": ("testserver", 80),
        }
        asyncio.run(app(scope, self.receive, self.send))
        return self.status


def problem(response: Any, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    assert response.headers["content-type"] == "application/problem+json"
    body: dict[str, Any] = response.json()
    assert body["code"] == code
    return body


def document_count(db: Session) -> int:
    case_id = sample_uuid("case", "case-1005")
    return (
        db.scalar(select(func.count()).select_from(Document).where(Document.case_id == case_id))
        or 0
    )


# --- upload: accepted types ---------------------------------------------------------------


@pytest.mark.parametrize("name", list(SAMPLES))
def test_uploads_each_supported_type(
    client: TestClient, seeded: Session, storage_root: Path, name: str
) -> None:
    content = SAMPLES[name]
    # The browser's claimed type is ignored; the server decides from the bytes.
    response = upload(client, name, content, ctype="application/x-evil")

    assert response.status_code == 201, response.text
    document = response.json()
    assert response.headers["location"] == f"/api/documents/{document['id']}"
    assert document["name"] == name
    assert document["sizeBytes"] == len(content)
    assert document["hasFile"] is True
    assert document["isSample"] is False
    assert document["uploadedOn"] == TODAY.isoformat()
    assert document["downloadUrl"] == f"/api/documents/{document['id']}/download"
    assert document["contentType"] != "application/x-evil"

    row = seeded.get(Document, uuid.UUID(document["id"]))
    assert row is not None and row.sha256 == hashlib.sha256(content).hexdigest()
    assert row.storage_key is not None
    files = stored_files(storage_root)
    assert [f.name for f in files] == [row.storage_key]  # stored under the key, not the name
    assert files[0].read_bytes() == content
    assert staging_files(storage_root) == []


def test_upload_metadata_labels(client: TestClient, seeded: Session) -> None:
    labels = {
        name: upload(client, name, content).json()["type"] for name, content in SAMPLES.items()
    }
    assert labels["Rejoinder.pdf"] == "PDF"
    assert labels["Reply.docx"] == labels["Legacy.doc"] == "Word document"
    assert labels["Notes.txt"] == "Text"
    assert labels["Exhibit.png"] == "Image"


def test_uploaded_document_listed_first(client: TestClient, seeded: Session) -> None:
    created = upload(client, "Rejoinder.pdf", PDF).json()

    listed = client.get(UPLOAD).json()
    assert listed[0]["id"] == created["id"]
    detail = client.get(f"/api/cases/{CASE}").json()
    assert detail["documents"][0]["id"] == created["id"]
    assert detail["documentCount"] == 5


# --- upload: rejected files ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("setup.exe", b"MZ\x90\x00"),
        ("drawing.svg", b"<svg xmlns='http://www.w3.org/2000/svg'/>"),
        ("page.html", b"<script>alert(1)</script>"),
        ("archive.zip", plain_zip_bytes()),
        ("noextension", PDF),
        (".pdf", PDF),
    ],
)
def test_rejects_unsupported_types(
    client: TestClient, seeded: Session, storage_root: Path, name: str, content: bytes
) -> None:
    problem(upload(client, name, content), 415, "unsupported-type")
    assert document_count(seeded) == 4
    assert stored_files(storage_root) == []


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("forged.pdf", png_bytes()),  # a PNG pretending to be a PDF
        ("forged.png", PDF),
        ("forged.jpg", b"GIF89a" + b"\x00" * 10),
        ("forged.gif", b"\xff\xd8\xff\xe0" + b"\x00" * 10),
        ("forged.webp", b"RIFF\x00\x00\x00\x00WAVEfmt "),
        ("forged.doc", b"Just some text, not an OLE file at all."),
        ("forged.docx", plain_zip_bytes()),  # a ZIP, but not a Word document
        ("broken.docx", b"PK\x03\x04 not really a zip"),
        ("binary.txt", b"text with a NUL\x00byte"),
        ("latin1.txt", "caf\xe9".encode("latin-1")),  # not valid UTF-8
        ("executable.txt", b"MZ\x90\x00\x03\x00\x00\x00\x04\x00"),
    ],
)
def test_rejects_content_that_does_not_match_the_extension(
    client: TestClient, seeded: Session, storage_root: Path, name: str, content: bytes
) -> None:
    problem(upload(client, name, content), 415, "content-mismatch")
    assert document_count(seeded) == 4
    assert stored_files(storage_root) == []
    assert staging_files(storage_root) == []


def test_rejects_empty_files(client: TestClient, seeded: Session, storage_root: Path) -> None:
    body = problem(upload(client, "Empty.pdf", b""), 422, "empty")
    assert body["detail"] == "Empty.pdf is empty."
    assert stored_files(storage_root) == [] and staging_files(storage_root) == []


def test_rejects_duplicate_names_case_insensitively(client: TestClient, seeded: Session) -> None:
    assert upload(client, "Rejoinder.pdf", PDF).status_code == 201
    problem(upload(client, "REJOINDER.PDF", PDF), 409, "duplicate")
    # Sample records count too: this name is already on the sample case.
    body = problem(upload(client, "cease and desist notice.pdf", PDF), 409, "duplicate")
    assert "already attached" in body["detail"]
    assert document_count(seeded) == 5


def test_requires_a_file_part(client: TestClient, seeded: Session) -> None:
    response = client.post(UPLOAD, data={"note": "no file here"})
    errors = problem(response, 422, "validation-error")["errors"]
    assert [e["field"] for e in errors] == ["file"]


@pytest.mark.parametrize("case_id", [str(uuid.uuid4()), "case-1005"])
def test_upload_to_unknown_case_is_404(client: TestClient, seeded: Session, case_id: str) -> None:
    response = client.post(
        f"/api/cases/{case_id}/documents", files={"file": ("A.pdf", PDF, "application/pdf")}
    )
    problem(response, 404, "case-not-found")


# --- filenames and paths ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("submitted", "stored"),
    [
        ("../../outside.pdf", "outside.pdf"),
        ("..\\..\\windows\\evil.pdf", "evil.pdf"),
        ("C:\\Windows\\System32\\drivers.pdf", "drivers.pdf"),
        ("/etc/passwd.pdf", "passwd.pdf"),
        ("  spaced name.pdf  ", "spaced name.pdf"),
        ("Plaint – अंतरिम आवेदन.pdf", "Plaint – अंतरिम आवेदन.pdf"),
    ],
)
def test_filenames_never_choose_the_storage_path(
    client: TestClient,
    seeded: Session,
    tmp_path: Path,
    storage_root: Path,
    submitted: str,
    stored: str,
) -> None:
    response = upload(client, submitted, PDF)

    assert response.status_code == 201, response.text
    assert response.json()["name"] == stored
    everything = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert everything, "the file should have been stored"
    for path in everything:
        assert storage_root in path.parents  # nothing was written outside the store
    row = seeded.get(Document, uuid.UUID(response.json()["id"]))
    assert row is not None
    assert [p.name for p in stored_files(storage_root)] == [row.storage_key]


def test_control_characters_are_removed(client: TestClient, seeded: Session) -> None:
    # U+202E (right-to-left override) could disguise "fdp.exe" as "exe.pdf".
    problem(upload(client, "invoice\u202efdp.exe", PDF), 415, "unsupported-type")
    # Browsers send '"' in a filename as %22 (WHATWG); it is decoded once.
    assert upload(client, 'Reply "final".pdf', PDF).json()["name"] == 'Reply "final".pdf'


@pytest.mark.parametrize(
    ("raw", "cleaned"),
    [
        ("re\x00port\x07.pdf", "report.pdf"),
        ("line%0Abreak%0D.pdf", "linebreak.pdf"),
        ("tab\there.pdf", "tabhere.pdf"),
        ("\u202eexe.pdf", "exe.pdf"),
        ("..", ""),
        ("   ", ""),
        (None, ""),
        ("100%41 legit.pdf", "100%41 legit.pdf"),  # only the browser escapes are decoded
        ("a" * 300 + ".pdf", "a" * 251 + ".pdf"),
    ],
)
def test_clean_filename(raw: str | None, cleaned: str) -> None:
    assert clean_filename(raw) == cleaned


# --- size limit -----------------------------------------------------------------------------


def test_upload_work_runs_off_the_event_loop(
    client: TestClient, seeded: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Saving an upload is synchronous database, disk and hashing work. It must
    # run in the thread pool, where no event loop runs, so it can't stall other
    # requests while it works.
    seen: dict[str, bool] = {}
    real = documents_service.upload_document

    def spy(*args: Any, **kwargs: Any) -> uuid.UUID:
        try:
            asyncio.get_running_loop()
            seen["on_event_loop"] = True
        except RuntimeError:
            seen["on_event_loop"] = False
        return real(*args, **kwargs)

    monkeypatch.setattr(documents_service, "upload_document", spy)

    assert upload(client, "Thread.pdf", PDF).status_code == 201
    assert seen == {"on_event_loop": False}


def test_rejects_files_over_the_limit(
    client: TestClient, seeded: Session, app: FastAPI, storage_root: Path
) -> None:
    app.state.upload_limit = 1000

    assert upload(client, "Exact.pdf", PDF + b"\n" * (1000 - len(PDF))).status_code == 201
    body = problem(upload(client, "Bigger.pdf", PDF + b"\n" * (1001 - len(PDF))), 413, "too-large")
    assert "upload limit" in body["detail"]
    assert document_count(seeded) == 5
    assert staging_files(storage_root) == []


def test_large_declared_body_is_refused_before_reading(
    client: TestClient, seeded: Session, app: FastAPI, storage_root: Path
) -> None:
    app.state.upload_limit = 1000
    boundary = "lexflowboundary"
    body = multipart(boundary, "Huge.pdf", PDF + b"0" * 500_000)  # far beyond the limit
    request = AsgiRequest(
        UPLOAD,
        boundary,
        [body],
        content_length=len(body),
        session=client.cookies["lexflow_session"],
    )

    status = request.send_to(app)

    assert status == 413
    assert request.body_reads == 0  # answered from the header alone
    assert stored_files(storage_root) == [] and staging_files(storage_root) == []


def test_streamed_body_without_length_stops_being_read_at_the_limit(
    client: TestClient, seeded: Session, app: FastAPI, storage_root: Path
) -> None:
    app.state.upload_limit = 1000
    allowed = 1000 + MULTIPART_OVERHEAD  # what the middleware lets through
    boundary = "lexflowboundary"
    body = multipart(boundary, "Stream.pdf", PDF + b"0" * (200 * 8192))
    chunks = [body[i : i + 8192] for i in range(0, len(body), 8192)]
    # chunked: no Content-Length
    request = AsgiRequest(UPLOAD, boundary, chunks, session=client.cookies["lexflow_session"])

    status = request.send_to(app)

    assert status == 413
    # Reading stopped at the first chunk past the limit, long before the end.
    assert request.bytes_read <= allowed + 8192
    assert request.body_reads < len(chunks) // 4
    assert stored_files(storage_root) == [] and staging_files(storage_root) == []
    assert document_count(seeded) == 4


def test_an_anonymous_upload_is_refused_before_any_body_is_read(
    seeded: Session, app: FastAPI, storage_root: Path
) -> None:
    boundary = "lexflowboundary"
    body = multipart(boundary, "Anonymous.pdf", PDF)
    request = AsgiRequest(UPLOAD, boundary, [body])  # no session cookie

    assert request.send_to(app) == 401
    assert request.body_reads == 0
    assert stored_files(storage_root) == [] and staging_files(storage_root) == []


def test_streamed_body_without_length_is_refused_through_the_client(
    client: TestClient, seeded: Session, app: FastAPI, storage_root: Path
) -> None:
    # The same request through the HTTP test client (which buffers the body
    # before the app sees it, so it can only check the outcome).
    app.state.upload_limit = 1000
    boundary = "lexflowboundary"

    def body() -> Iterator[bytes]:
        yield multipart(boundary, "Stream.pdf", PDF + b"0" * (200 * 8192))

    response = client.post(
        UPLOAD,
        content=body(),
        headers={"content-type": f"multipart/form-data; boundary={boundary}"},
    )

    problem(response, 413, "too-large")
    assert stored_files(storage_root) == [] and staging_files(storage_root) == []


# --- clean-up when storage or the database fails ------------------------------------


def test_storage_failure_leaves_no_record_or_file(
    client: TestClient,
    seeded: Session,
    app: FastAPI,
    storage_root: Path,
) -> None:
    class BrokenStorage(LocalDiskStorage):
        def put(self, key: str, staged: Path) -> None:
            raise OSError("disk full")

    app.dependency_overrides[get_storage] = lambda: BrokenStorage(storage_root)

    problem(upload(client, "Rejoinder.pdf", PDF), 500, "internal-error")
    assert document_count(seeded) == 4
    assert stored_files(storage_root) == [] and staging_files(storage_root) == []


def test_commit_failure_removes_the_stored_file(
    client: TestClient,
    seeded: Session,
    storage_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_commit() -> None:
        raise RuntimeError("commit failed")

    monkeypatch.setattr(seeded, "commit", failing_commit)

    problem(upload(client, "Rejoinder.pdf", PDF), 500, "internal-error")
    monkeypatch.undo()
    assert document_count(seeded) == 4
    assert stored_files(storage_root) == [] and staging_files(storage_root) == []


# --- download --------------------------------------------------------------------------------


def test_download_returns_exact_bytes_with_safe_headers(
    client: TestClient, seeded: Session
) -> None:
    created = upload(client, "Rejoinder.pdf", PDF).json()

    response = client.get(created["downloadUrl"])

    assert response.status_code == 200
    assert response.content == PDF
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-length"] == str(len(PDF))
    assert response.headers["content-disposition"] == (
        "inline; filename=\"Rejoinder.pdf\"; filename*=UTF-8''Rejoinder.pdf"
    )


def test_download_disposition_by_type(client: TestClient, seeded: Session) -> None:
    image = client.get(upload(client, "Exhibit.png", png_bytes()).json()["downloadUrl"])
    assert image.headers["content-disposition"].startswith("inline;")
    assert image.headers["content-security-policy"].startswith("sandbox")

    text = client.get(upload(client, "Notes.txt", SAMPLES["Notes.txt"]).json()["downloadUrl"])
    assert text.headers["content-type"] == "text/plain; charset=utf-8"
    assert "sandbox" in text.headers["content-security-policy"]

    word = client.get(upload(client, "Reply.docx", docx_bytes()).json()["downloadUrl"])
    assert word.headers["content-disposition"].startswith("attachment;")
    # Downloaded, never rendered by the browser, so no sandbox policy is needed.
    assert "content-security-policy" not in word.headers
    assert word.content == docx_bytes()


def test_download_encodes_unicode_and_quotes_safely(client: TestClient, seeded: Session) -> None:
    name = 'Plaint "draft" – अंतरिम.pdf'
    created = upload(client, name, PDF).json()

    disposition = client.get(created["downloadUrl"]).headers["content-disposition"]

    assert 'filename="Plaint draft  .pdf"' in disposition  # ASCII fallback, quotes removed
    assert "filename*=UTF-8''Plaint%20%22draft%22%20%E2%80%93" in disposition


def test_download_errors(client: TestClient, seeded: Session, storage_root: Path) -> None:
    problem(client.get(f"/api/documents/{uuid.uuid4()}/download"), 404, "document-not-found")
    problem(client.get("/api/documents/d-1/download"), 404, "document-not-found")

    sample = sample_uuid("document", "d-18")
    problem(client.get(f"/api/documents/{sample}/download"), 404, "no-file")

    created = upload(client, "Rejoinder.pdf", PDF).json()
    for path in stored_files(storage_root):
        path.unlink()
    problem(client.get(created["downloadUrl"]), 404, "file-missing")


# --- delete --------------------------------------------------------------------------------


def test_delete_hides_the_document_but_keeps_record_and_file(
    client: TestClient, seeded: Session, storage_root: Path
) -> None:
    created = upload(client, "Rejoinder.pdf", PDF).json()
    case_path = f"/api/cases/{CASE}"
    count_before = client.get(case_path).json()["documentCount"]

    response = client.delete(f"/api/documents/{created['id']}")

    assert response.status_code == 204
    assert response.content == b""
    # Kept, marked deleted, with its file, so it can be restored.
    seeded.expire_all()
    row = seeded.get(Document, uuid.UUID(created["id"]))
    assert row is not None and row.deleted_at is not None and row.deleted_by_id is not None
    assert len(stored_files(storage_root)) == 1
    # Gone from every ordinary read.
    detail = client.get(case_path).json()
    assert created["id"] not in {d["id"] for d in detail["documents"]}
    assert detail["documentCount"] == count_before - 1
    problem(client.delete(f"/api/documents/{created['id']}"), 404, "document-not-found")
    problem(client.get(created["downloadUrl"]), 404, "document-not-found")


def test_delete_sample_record_without_file(client: TestClient, seeded: Session) -> None:
    sample = sample_uuid("document", "d-18")

    assert client.delete(f"/api/documents/{sample}").status_code == 204
    seeded.expire_all()
    row = seeded.get(Document, sample)
    assert row is not None and row.deleted_at is not None


# --- persistence --------------------------------------------------------------------------


def test_files_survive_an_application_restart(
    client: TestClient, seeded: Session, storage_root: Path
) -> None:
    from lexflow.db import get_session
    from lexflow.main import create_app

    created = upload(client, "Rejoinder.pdf", PDF).json()

    restarted = create_app()  # a new application instance, new storage object
    restarted.dependency_overrides[get_session] = lambda: seeded
    restarted.dependency_overrides[get_storage] = lambda: LocalDiskStorage(storage_root)
    # The session also survives the restart: it lives in the database.
    with TestClient(restarted, cookies=dict(client.cookies)) as fresh:
        response = fresh.get(created["downloadUrl"])
        assert response.status_code == 200 and response.content == PDF
        assert fresh.get(f"/api/cases/{CASE}").json()["documents"][0]["id"] == created["id"]
