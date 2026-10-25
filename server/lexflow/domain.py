"""Allowed values shared by the database constraints and the API schemas.

These mirror the TypeScript unions in ``src/types/index.ts``; the generated
OpenAPI types keep the two in step.
"""

from __future__ import annotations

from typing import Literal, get_args

UserRole = Literal["Administrator", "Advocate", "Paralegal", "Client"]
CaseStatus = Literal["Open", "In Progress", "On Hold", "Closed"]
CasePriority = Literal["Low", "Medium", "High", "Critical"]
PracticeArea = Literal[
    "Corporate / Commercial",
    "Civil",
    "Criminal",
    "Family",
    "Intellectual Property",
    "Constitutional / Administrative",
    "Real Estate",
    "Employment & Labour",
]

AuditOutcome = Literal["success", "denied", "failed"]
HearingStatus = Literal["Scheduled", "Cancelled"]
# Text extraction of a document (Phase 3), and whether its chunks are indexed
# for search (embeddings).
ExtractionStatus = Literal["queued", "processing", "ready", "failed", "unsupported"]
IndexStatus = Literal["disabled", "pending", "indexed", "failed"]
# An AI case analysis run (Phase 5).
AnalysisStatus = Literal["queued", "running", "ready", "failed"]
# Phase 6: a lawyer's decision on one finding of an analysis run.
ReviewStatus = Literal["unreviewed", "accepted", "edited", "rejected"]
FindingKind = Literal["fact", "issue", "precedent", "contradiction"]
# Phase 7 (synthetic engineering demo): an outcome assessment of a reviewed
# analysis run, how each cited precedent bears on the position, and the
# assessment's uncertainty category. Categories, never numbers.
AssessmentStatus = Literal["ready", "insufficient", "failed"]
AssessmentStance = Literal["supports", "cuts_against", "does_not_resolve"]
AssessmentUncertainty = Literal[
    "insufficient_basis", "mixed_evidence", "limited_support", "evidence_supports_position"
]

USER_ROLES: tuple[str, ...] = get_args(UserRole)
AUDIT_OUTCOMES: tuple[str, ...] = get_args(AuditOutcome)

ADMINISTRATOR, ADVOCATE, PARALEGAL, CLIENT = "Administrator", "Advocate", "Paralegal", "Client"
STAFF_ROLES = frozenset({ADMINISTRATOR, ADVOCATE, PARALEGAL})
CASE_STATUSES: tuple[str, ...] = get_args(CaseStatus)
CASE_PRIORITIES: tuple[str, ...] = get_args(CasePriority)
PRACTICE_AREAS: tuple[str, ...] = get_args(PracticeArea)
HEARING_SCHEDULED, HEARING_CANCELLED = "Scheduled", "Cancelled"
EXTRACTION_STATUSES: tuple[str, ...] = get_args(ExtractionStatus)
INDEX_STATUSES: tuple[str, ...] = get_args(IndexStatus)
EXTRACTION_REASON_MAX = 500
ANALYSIS_STATUSES: tuple[str, ...] = get_args(AnalysisStatus)
ANALYSIS_REASON_MAX = 500
REVIEW_STATUSES: tuple[str, ...] = get_args(ReviewStatus)
FINDING_KINDS: tuple[str, ...] = get_args(FindingKind)
# The id prefix of each kind of finding in an analysis result (F1, I1, P1, C1).
FINDING_PREFIX = {"fact": "F", "issue": "I", "precedent": "P", "contradiction": "C"}
REVIEW_TEXT_MAX = 2_000
REVIEW_NOTE_MAX = 2_000
ASSESSMENT_STATUSES: tuple[str, ...] = get_args(AssessmentStatus)
ASSESSMENT_STANCES: tuple[str, ...] = get_args(AssessmentStance)
ASSESSMENT_UNCERTAINTIES: tuple[str, ...] = get_args(AssessmentUncertainty)
ASSESSMENT_REASON_MAX = 500

TITLE_MIN, TITLE_MAX = 4, 300
DESCRIPTION_MIN, DESCRIPTION_MAX = 10, 10_000
SHORT_TEXT_MAX = 300
DOCUMENT_NAME_MAX = 255
HEARING_TEXT_MAX = 200  # court and purpose
CANCELLATION_REASON_MAX = 500
