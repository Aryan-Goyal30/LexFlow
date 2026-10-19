"""Case teams (Phase 2): who besides the lead advocate works on a case.

Advocates see the cases they lead or are an associate on; Paralegals see the
cases they are assigned to. ``member_role`` is ``associate`` or ``paralegal``.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "case_members",
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("member_role", sa.Text(), nullable=False),
        sa.Column("added_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "member_role IN ('associate', 'paralegal')",
            name=op.f("ck_case_members_member_role_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["added_by_id"],
            ["users.id"],
            name=op.f("fk_case_members_added_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
            name=op.f("fk_case_members_case_id_cases"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_case_members_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("case_id", "user_id", name=op.f("pk_case_members")),
    )
    op.create_index(op.f("ix_case_members_user_id"), "case_members", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_case_members_user_id"), table_name="case_members")
    op.drop_table("case_members")
