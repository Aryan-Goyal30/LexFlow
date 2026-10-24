"""SYNTHETIC analysis runs for the Phase 6 review tests.

``ready_run`` stores a run as the worker would after validation: a ready
result with one finding of each kind, and its evidence record. Nothing here
contacts a provider.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from lexflow.analysis.runs import pipeline_record
from lexflow.models import AnalysisRun

DOC = uuid.UUID("00000000-0000-4000-8000-0000000006d1")
CHUNK = uuid.UUID("00000000-0000-4000-8000-0000000006c1")
JUDGMENT = uuid.UUID("00000000-0000-4000-8000-0000000006e1")
JCHUNK = uuid.UUID("00000000-0000-4000-8000-0000000006f1")


def source(
    quote: str = "SYNTHETIC: the mark was registered in 2015", **extra: Any
) -> dict[str, Any]:
    return {
        "evidenceId": "D1",
        "documentId": str(DOC),
        "documentName": "SYNTHETIC Plaint.pdf",
        "chunkId": str(CHUNK),
        "sectionNumber": 2,
        "pageNumber": 2,
        "quote": quote,
        **extra,
    }


def result() -> dict[str, Any]:
    """A validated result (as stored by the worker) with every kind of finding."""
    return {
        "facts": [
            {
                "id": "F1",
                "statement": "SYNTHETIC: the mark was registered in 2015.",
                "source": source(),
            },
            {
                "id": "F2",
                "statement": "SYNTHETIC: the reply gives 2017 as the first use.",
                "source": source("SYNTHETIC: first use only in 2017"),
            },
        ],
        "issues": [
            {
                "id": "I1",
                "question": "SYNTHETIC: which first-use date is right?",
                "factIds": ["F1", "F2"],
            }
        ],
        "precedents": [
            {
                "id": "P1",
                "evidenceId": "J1",
                "judgmentId": str(JUDGMENT),
                "title": "Asha Rao v. Bharat Traders (SYNTHETIC)",
                "court": "SYNTHETIC District Court (test fixture)",
                "citation": "(SYN) 2019 TEST 101",
                "year": 2019,
                "synthetic": True,
                "retrievalRank": 1,
                "passage": {"chunkId": str(JCHUNK), "sectionNumber": 3, "pageNumber": 3},
                "summary": "SYNTHETIC: prior use is weighed against adoption.",
                "similarities": ["Both concern prior use."],
                "differences": ["Different goods."],
            }
        ],
        "contradictions": [
            {
                "id": "C1",
                "description": "SYNTHETIC: first use is 2015 in the plaint and 2017 in the reply.",
                "sources": [source(), source("SYNTHETIC: first use only in 2017")],
            }
        ],
        "insufficientEvidence": False,
        "insufficientReason": None,
        "precedentsAvailable": True,
        "removed": {"count": 0, "reasons": []},
    }


def evidence_record() -> dict[str, Any]:
    return {
        "documentsSelected": 1,
        "documentsWithoutText": [],
        "characters": 400,
        "truncated": False,
        "items": {
            "D1": {
                "kind": "document",
                "documentId": str(DOC),
                "chunkId": str(CHUNK),
                "chunkNumber": 2,
                "sectionNumber": 2,
                "pageNumber": 2,
                "contentSha256": "0" * 64,
            },
            "J1": {
                "kind": "judgment",
                "judgmentId": str(JUDGMENT),
                "chunkId": str(JCHUNK),
                "sectionNumber": 3,
                "pageNumber": 3,
                "rank": 1,
                "contentSha256": "1" * 64,
            },
        },
        "pipeline": pipeline_record(),
    }


def ready_run(
    db: Session, case_id: uuid.UUID, *, requested_by: uuid.UUID | None = None
) -> AnalysisRun:
    now = datetime.now(UTC)
    run = AnalysisRun(
        case_id=case_id,
        requested_by_id=requested_by,
        status="ready",
        provider="scripted",
        model="scripted-v1",
        prompt_version="case-analysis-v2",
        selection={"documentIds": [str(DOC)], "limits": {}},
        evidence=evidence_record(),
        result=result(),
        removed={"count": 0, "reasons": []},
        usage={},
        created_at=now,
        started_at=now,
        finished_at=now,
    )
    db.add(run)
    db.commit()
    return run
