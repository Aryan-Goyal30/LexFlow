"""Who may see and do what: the single place where access rules live.

A user's *relationship* to a case decides everything:

=============  ===========================================================
ADMIN          any Administrator: every case
LEAD           the case's lead advocate
ASSOCIATE      an Advocate added to the case team
PARALEGAL      a Paralegal assigned to the case
CLIENT         a Client user whose client record owns the case (portal only)
NONE           anyone else
=============  ===========================================================

Rules (``ALLOWED``) map each action to the relationships that may do it. Staff
routes treat CLIENT like NONE: clients use the separate portal routes.

Refusals: a case the user may not see answers 404 ``case-not-found`` (the same
as a case that does not exist, so ids cannot be probed); a case they can see
but an action they may not take answers 403 ``forbidden``. Both are audited.
An archived case can be viewed but not changed (409 ``case-archived``) until an
Administrator restores it.
"""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import ColumnElement, exists, false, or_, select, true
from sqlalchemy.orm import Session

from lexflow.audit import AuditLog
from lexflow.domain import ADMINISTRATOR, ADVOCATE, CLIENT, PARALEGAL
from lexflow.errors import FieldError, ProblemError
from lexflow.models import Case, CaseMember, Document, Hearing, User

CASE_NOT_FOUND = "No case with this id exists."


class Relation(StrEnum):
    ADMIN = "admin"
    LEAD = "lead"
    ASSOCIATE = "associate"
    PARALEGAL = "paralegal"
    CLIENT = "client"
    NONE = "none"


class Action(StrEnum):
    VIEW = "view"
    EDIT_DETAILS = "edit-details"  # title, summary, practice area, priority
    EDIT_LISTING = "edit-listing"  # court and opposing party
    CHANGE_STATUS = "change-status"
    CHANGE_LEAD = "change-lead"
    CHANGE_CLIENT = "change-client"
    MANAGE_TEAM = "manage-team"
    ARCHIVE = "archive"
    MANAGE_HEARINGS = "manage-hearings"
    UPLOAD_DOCUMENT = "upload-document"
    DELETE_DOCUMENT = "delete-document"
    RESTORE_DOCUMENT = "restore-document"
    VIEW_DELETED_DOCUMENTS = "view-deleted-documents"
    SHARE_DOCUMENT = "share-document"
    RUN_ANALYSIS = "run-analysis"  # start an AI case analysis (Phase 5)


_STAFF_ON_CASE = frozenset({Relation.ADMIN, Relation.LEAD, Relation.ASSOCIATE, Relation.PARALEGAL})
_ADVOCATES_ON_CASE = frozenset({Relation.ADMIN, Relation.LEAD, Relation.ASSOCIATE})

ALLOWED: dict[Action, frozenset[Relation]] = {
    Action.VIEW: _STAFF_ON_CASE,
    Action.EDIT_DETAILS: _ADVOCATES_ON_CASE,
    # Paralegals keep listing details current as matters are filed and listed.
    Action.EDIT_LISTING: _STAFF_ON_CASE,
    Action.CHANGE_STATUS: _ADVOCATES_ON_CASE,
    Action.CHANGE_LEAD: frozenset({Relation.ADMIN}),
    Action.CHANGE_CLIENT: frozenset({Relation.ADMIN}),
    Action.MANAGE_TEAM: frozenset({Relation.ADMIN, Relation.LEAD}),
    Action.ARCHIVE: frozenset({Relation.ADMIN}),
    Action.MANAGE_HEARINGS: _STAFF_ON_CASE,
    Action.UPLOAD_DOCUMENT: _STAFF_ON_CASE,
    Action.DELETE_DOCUMENT: frozenset({Relation.ADMIN, Relation.LEAD}),
    Action.RESTORE_DOCUMENT: frozenset({Relation.ADMIN, Relation.LEAD}),
    # Those who may restore may see what there is to restore.
    Action.VIEW_DELETED_DOCUMENTS: frozenset({Relation.ADMIN, Relation.LEAD}),
    Action.SHARE_DOCUMENT: _ADVOCATES_ON_CASE,
    # Owner decision D4 (Phase 5): advocates on the case and Administrators;
    # paralegals may read results (VIEW) but not send case text to a provider.
    Action.RUN_ANALYSIS: _ADVOCATES_ON_CASE,
}

# PATCH /api/cases/{id}: the action each field needs.
FIELD_ACTIONS: dict[str, Action] = {
    "title": Action.EDIT_DETAILS,
    "description": Action.EDIT_DETAILS,
    "practice_area": Action.EDIT_DETAILS,
    "priority": Action.EDIT_DETAILS,
    "court_name": Action.EDIT_LISTING,
    "opposing_party": Action.EDIT_LISTING,
    "status": Action.CHANGE_STATUS,
    "lead_advocate_id": Action.CHANGE_LEAD,
    "client_id": Action.CHANGE_CLIENT,
}
CAMEL = {
    "title": "title",
    "description": "description",
    "practice_area": "practiceArea",
    "priority": "priority",
    "court_name": "courtName",
    "opposing_party": "opposingParty",
    "status": "status",
    "lead_advocate_id": "leadAdvocateId",
    "client_id": "clientId",
}


def relation(session: Session, user: User, case: Case) -> Relation:
    if user.role == ADMINISTRATOR:
        return Relation.ADMIN
    if user.role == CLIENT:
        return Relation.CLIENT if user.client_id == case.client_id else Relation.NONE
    if user.role == ADVOCATE and case.lead_advocate_id == user.id:
        return Relation.LEAD
    member = session.get(CaseMember, (case.id, user.id))
    if member is not None:
        if user.role == ADVOCATE and member.member_role == "associate":
            return Relation.ASSOCIATE
        if user.role == PARALEGAL and member.member_role == "paralegal":
            return Relation.PARALEGAL
    return Relation.NONE


def allows(rel: Relation, action: Action) -> bool:
    return rel in ALLOWED[action]


def visible_cases(user: User) -> ColumnElement[bool]:
    """A WHERE clause selecting the cases a staff member may see."""
    is_member = exists(
        select(CaseMember.case_id).where(
            CaseMember.case_id == Case.id, CaseMember.user_id == user.id
        )
    )
    if user.role == ADMINISTRATOR:
        return true()
    if user.role == ADVOCATE:
        return or_(Case.lead_advocate_id == user.id, is_member)
    if user.role == PARALEGAL:
        return is_member
    return false()  # clients see cases only through the portal


def archived() -> ProblemError:
    return ProblemError(
        409,
        "case-archived",
        "This case is archived. An administrator must restore it before it can be changed.",
    )


def check_not_archived(case: Case, action: Action) -> None:
    read_only = (Action.VIEW, Action.VIEW_DELETED_DOCUMENTS, Action.ARCHIVE)
    if action not in read_only and case.archived_at is not None:
        raise archived()


def not_found() -> ProblemError:
    return ProblemError(404, "case-not-found", CASE_NOT_FOUND)


def forbidden(detail: str = "You do not have permission to do this.") -> ProblemError:
    return ProblemError(403, "forbidden", detail)


def denied(
    audit: AuditLog,
    user: User,
    case: Case,
    action: Action,
    *,
    target_type: str = "case",
    target_id: uuid.UUID | None = None,
) -> None:
    audit.record(
        "access.denied",
        actor=user,
        outcome="denied",
        target_type=target_type,
        target_id=target_id or case.id,
        case_id=case.id,
        details={"action": action.value},
    )


def load_case(
    session: Session,
    user: User,
    case_id: uuid.UUID,
    action: Action,
    audit: AuditLog,
    *,
    lock: bool = False,
) -> tuple[Case, Relation]:
    """The case, if ``user`` may take ``action`` on it; else 404 or 403 (audited)."""
    case = session.get(Case, case_id, with_for_update=lock)
    if case is None:
        raise not_found()
    rel = relation(session, user, case)
    if not allows(rel, Action.VIEW):
        denied(audit, user, case, action)
        raise not_found()
    if not allows(rel, action):
        denied(audit, user, case, action)
        raise forbidden()
    check_not_archived(case, action)
    return case, rel


def check_fields(
    audit: AuditLog, user: User, case: Case, rel: Relation, fields: dict[str, Any]
) -> None:
    """Refuse a partial update that touches any field this user may not change.

    Checked before anything is applied, so a refused request changes nothing.
    Fields are refused even when the new value equals the old one.
    """
    refused = [name for name in fields if not allows(rel, FIELD_ACTIONS[name])]
    if refused:
        audit.record(
            "access.denied",
            actor=user,
            outcome="denied",
            target_type="case",
            target_id=case.id,
            case_id=case.id,
            details={"action": "update", "fields": [CAMEL[name] for name in refused]},
        )
        raise ProblemError(
            403,
            "field-not-permitted",
            "You cannot change some of these fields.",
            errors=[
                FieldError(field=CAMEL[name], message="You cannot change this field.")
                for name in refused
            ],
        )


def permissions(rel: Relation, *, is_archived: bool = False) -> dict[str, Any]:
    """What the user may do on a case, for the client to show the right controls.

    Only a convenience for the screens: the server checks every action again.
    On an archived case nothing may change except restoring it.
    """

    def may(action: Action) -> bool:
        return allows(rel, action) and not is_archived

    editable = [CAMEL[name] for name, action in FIELD_ACTIONS.items() if may(action)]
    return {
        "relation": rel.value,
        "editable_fields": editable,
        "can_change_status": may(Action.CHANGE_STATUS),
        "can_manage_team": may(Action.MANAGE_TEAM),
        "can_archive": allows(rel, Action.ARCHIVE),
        "can_manage_hearings": may(Action.MANAGE_HEARINGS),
        "can_upload_documents": may(Action.UPLOAD_DOCUMENT),
        "can_delete_documents": may(Action.DELETE_DOCUMENT),
        "can_restore_documents": may(Action.RESTORE_DOCUMENT),
        "can_share_documents": may(Action.SHARE_DOCUMENT),
        "can_run_analysis": may(Action.RUN_ANALYSIS),
    }


DOCUMENT_NOT_FOUND = "No document with this id exists."
HEARING_NOT_FOUND = "No hearing with this id exists."


def load_document(
    session: Session,
    user: User,
    document_id: uuid.UUID,
    action: Action,
    audit: AuditLog,
    *,
    include_deleted: bool = False,
    lock: bool = False,
) -> tuple[Document, Case, Relation]:
    """A document, if ``user`` may take ``action`` on its case; else 404 or 403.

    A document on a case the user may not see is reported exactly like a
    document that does not exist. So is a deleted document, unless
    ``include_deleted`` (restoring needs to find it).
    """
    document = session.get(Document, document_id, with_for_update=lock)
    case = session.get(Case, document.case_id) if document is not None else None
    if document is None or case is None:
        raise ProblemError(404, "document-not-found", DOCUMENT_NOT_FOUND)
    rel = relation(session, user, case)
    if not allows(rel, Action.VIEW):
        denied(audit, user, case, action, target_type="document", target_id=document.id)
        raise ProblemError(404, "document-not-found", DOCUMENT_NOT_FOUND)
    if not allows(rel, action):
        denied(audit, user, case, action, target_type="document", target_id=document.id)
        raise forbidden()
    if document.deleted_at is not None and not include_deleted:
        raise ProblemError(404, "document-not-found", DOCUMENT_NOT_FOUND)
    check_not_archived(case, action)
    return document, case, rel


def load_hearing(
    session: Session,
    user: User,
    hearing_id: uuid.UUID,
    action: Action,
    audit: AuditLog,
    *,
    lock: bool = False,
) -> tuple[Hearing, Case, Relation]:
    """A hearing, if ``user`` may take ``action`` on its case; else 404 or 403.

    A hearing on a case the user may not see is reported like one that does
    not exist.
    """
    hearing = session.get(Hearing, hearing_id, with_for_update=lock)
    case = session.get(Case, hearing.case_id) if hearing is not None else None
    if hearing is None or case is None:
        raise ProblemError(404, "hearing-not-found", HEARING_NOT_FOUND)
    rel = relation(session, user, case)
    if not allows(rel, Action.VIEW):
        denied(audit, user, case, action, target_type="hearing", target_id=hearing.id)
        raise ProblemError(404, "hearing-not-found", HEARING_NOT_FOUND)
    if not allows(rel, action):
        denied(audit, user, case, action, target_type="hearing", target_id=hearing.id)
        raise forbidden()
    check_not_archived(case, action)
    return hearing, case, rel
