"""Smoke test: the real worker and model on the live PostgreSQL server, e2e data only.

    server\\.venv\\Scripts\\python docs/verification/embeddings/live_worker_smoke.py

Runs against the test-scoped database ``lexflow_e2e`` (FICTIONAL e2e data; the
name must contain "e2e"), never ``lexflow``. Steps: the explicit
``queue-indexing`` command (preview, then ``--confirm N``), one run of
``python -m lexflow.worker --once`` with ``LEXFLOW_EMBEDDINGS=local``, then
checks that every queued document has one vector per chunk from the pinned
model, and that a semantic search returns passages whose offsets match the
stored text. Prints names, counts and scores only; never connection details.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine, func, make_url, select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "server"
PY = str(SERVER / ".venv" / "Scripts" / "python.exe")
sys.path.insert(0, str(SERVER))

url = make_url(str(dotenv_values(SERVER / ".env")["DATABASE_URL"])).set(
    database="lexflow_e2e"
)
if "e2e" not in (url.database or ""):
    raise SystemExit("refusing: not the e2e database")
env = {
    **os.environ,
    "DATABASE_URL": url.render_as_string(hide_password=False),
    "LEXFLOW_EMBEDDINGS": "local",
    "LEXFLOW_UPLOAD_DIR": str(SERVER / "var" / "e2e-uploads"),
    "LEXFLOW_ENV": "development",
}


def run(*args: str) -> str:
    result = subprocess.run(
        [PY, "-m", *args],
        cwd=SERVER,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    if result.returncode != 0:
        raise SystemExit(f"{' '.join(args)} failed ({result.returncode}):\n{output}")
    return output


preview = run("lexflow.cli.models", "queue-indexing")
print(preview.strip())
match = re.search(r"--confirm (\d+)", preview)
if match:
    print(
        run("lexflow.cli.models", "queue-indexing", "--confirm", match.group(1)).strip()
    )
worker_log = run("lexflow.worker", "--once")
print("\n".join(line.split(" ", 3)[-1] for line in worker_log.strip().splitlines()))

os.environ.update(
    {k: v for k, v in env.items() if k.startswith(("DATABASE_URL", "LEXFLOW_"))}
)
from lexflow.config import get_settings
from lexflow.embeddings import MODEL_KEY, provider_for
from lexflow.models import (
    Document,
    DocumentChunk,
    DocumentChunkEmbedding,
    DocumentExtraction,
    DocumentSection,
)
from lexflow.services import retrieval

get_settings.cache_clear()
provider = provider_for(get_settings())
assert provider is not None
engine = create_engine(url)
ok = True
with Session(engine) as session:
    assert session.scalar(select(func.current_database())) == "lexflow_e2e"
    jobs = session.execute(
        select(DocumentExtraction, Document.name)
        .join(Document, Document.id == DocumentExtraction.document_id)
        .where(DocumentExtraction.status == "ready")
        .order_by(Document.name)
    ).all()
    for job, name in jobs:
        vectors = session.scalar(
            select(func.count())
            .select_from(DocumentChunkEmbedding)
            .where(
                DocumentChunkEmbedding.document_id == job.document_id,
                DocumentChunkEmbedding.model == MODEL_KEY,
            )
        )
        good = job.index_status == "indexed" and job.embedding_model == MODEL_KEY
        good = good and vectors == job.chunk_count
        ok &= good
        print(
            f"{name}: {job.index_status}, {vectors}/{job.chunk_count} vectors {'OK' if good else 'FAIL'}"
        )

    case_id = session.scalar(
        select(Document.case_id).where(Document.name == "e2e-notes.txt").limit(1)
    )
    assert case_id is not None
    hits = retrieval.semantic(session, provider, case_id, "notes about the client", 5)
    print(f"semantic search: {len(hits)} result(s)")
    for hit in hits:
        section = session.get(DocumentSection, (hit.document_id, hit.section_number))
        chunk = session.get(DocumentChunk, hit.chunk_id)
        exact = (
            section is not None
            and chunk is not None
            and section.text[hit.char_start : hit.char_end] == hit.text == chunk.text
        )
        ok &= exact
        print(
            f"  {hit.score:.3f} {hit.document_name} chunk {hit.chunk_number} offsets {'exact' if exact else 'WRONG'}"
        )
    deleted = {
        d
        for (d,) in session.execute(
            select(Document.id).where(
                Document.case_id == case_id, Document.deleted_at.is_not(None)
            )
        )
    }
    ok &= not any(hit.document_id in deleted for hit in hits)
engine.dispose()
print("SMOKE TEST", "PASSED" if ok else "FAILED")
sys.exit(0 if ok else 1)
