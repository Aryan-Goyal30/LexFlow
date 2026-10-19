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

USER_ROLES: tuple[str, ...] = get_args(UserRole)
CASE_STATUSES: tuple[str, ...] = get_args(CaseStatus)
CASE_PRIORITIES: tuple[str, ...] = get_args(CasePriority)
PRACTICE_AREAS: tuple[str, ...] = get_args(PracticeArea)

TITLE_MIN, TITLE_MAX = 4, 300
DESCRIPTION_MIN, DESCRIPTION_MAX = 10, 10_000
SHORT_TEXT_MAX = 300
DOCUMENT_NAME_MAX = 255
