"""Archiving cases (Phase 2): cases are archived, never deleted.

An archived case keeps all its records but is read-only and hidden from
default lists until an Administrator restores it.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("cases", sa.Column("archived_by_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_cases_archived_by_id_users"),
        "cases",
        "users",
        ["archived_by_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_cases_archived_by_id_users"), "cases", type_="foreignkey")
    op.drop_column("cases", "archived_by_id")
    op.drop_column("cases", "archived_at")
