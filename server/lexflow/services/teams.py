"""Case teams: associates (Advocates) and Paralegals working with the lead advocate.

Only an Administrator or the case's lead advocate may change the team
(``authz.Action.MANAGE_TEAM``). A member's role on the team follows their user
role: an Advocate joins as an associate, a Paralegal as a paralegal. Changing
the lead is a separate, Administrator-only change of the case itself.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from lexflow import authz
from lexflow.audit import AuditLog
from lexflow.authz import Action, Relation
from lexflow.domain import ADVOCATE, PARALEGAL
from lexflow.errors import FieldError, ProblemError
from lexflow.models import CaseMember, TimelineEvent, User

ROLE_LABELS = {"associate": "an associate advocate", "paralegal": "a paralegal"}


def _invalid(message: str) -> ProblemError:
    return ProblemError(
        422,
        "validation-error",
        "Correct the highlighted fields and try again.",
        title="Some fields are invalid",
        errors=[FieldError(field="userId", message=message)],
    )


def add_member(
    session: Session,
    case_id: uuid.UUID,
    member_id: uuid.UUID,
    *,
    today: date,
    user: User,
    audit: AuditLog,
) -> Relation:
    case, rel = authz.load_case(session, user, case_id, Action.MANAGE_TEAM, audit, lock=True)
    member = session.get(User, member_id)
    if member is None or not member.is_active or member.role not in (ADVOCATE, PARALEGAL):
        raise _invalid("Choose an active advocate or paralegal.")
    if member.id == case.lead_advocate_id:
        raise _invalid("The lead advocate already leads this case.")
    if session.get(CaseMember, (case.id, member.id)) is not None:
        return rel  # already on the team: nothing to change

    member_role = "associate" if member.role == ADVOCATE else "paralegal"
    session.add(
        CaseMember(case_id=case.id, user_id=member.id, member_role=member_role, added_by_id=user.id)
    )
    session.add(
        TimelineEvent(
            case_id=case.id,
            event_date=today,
            label="Case team updated",
            description=f"{member.name} joined the case team as {ROLE_LABELS[member_role]}.",
            actor_id=user.id,
        )
    )
    session.commit()
    audit.record(
        "case.team_member_added",
        actor=user,
        target_type="user",
        target_id=member.id,
        case_id=case.id,
        details={"memberRole": member_role},
    )
    return rel


def remove_member(
    session: Session,
    case_id: uuid.UUID,
    member_id: uuid.UUID,
    *,
    today: date,
    user: User,
    audit: AuditLog,
) -> Relation:
    case, rel = authz.load_case(session, user, case_id, Action.MANAGE_TEAM, audit, lock=True)
    membership = session.get(CaseMember, (case.id, member_id))
    if membership is None:
        raise ProblemError(404, "member-not-found", "That person is not on this case team.")
    member = session.get(User, member_id)
    session.delete(membership)
    session.add(
        TimelineEvent(
            case_id=case.id,
            event_date=today,
            label="Case team updated",
            description=f"{member.name if member else 'A member'} left the case team.",
            actor_id=user.id,
        )
    )
    session.commit()
    audit.record(
        "case.team_member_removed",
        actor=user,
        target_type="user",
        target_id=member_id,
        case_id=case.id,
        details={"memberRole": membership.member_role},
    )
    return rel
