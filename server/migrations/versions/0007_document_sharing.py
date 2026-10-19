"""Documents shared with the client, explicitly (Phase 2b, client portal).

Nothing is visible to a client unless an advocate on the case shares it. A
deleted document is never shared: deleting stops sharing, and restoring does
not share it again.

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents", sa.Column("shared_with_client_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("documents", sa.Column("shared_by_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_documents_shared_by_id_users"),
        "documents",
        "users",
        ["shared_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        op.f("ck_documents_shared_by_needs_shared_at"),
        "documents",
        "shared_by_id IS NULL OR shared_with_client_at IS NOT NULL",
    )
    op.create_check_constraint(
        op.f("ck_documents_deleted_never_shared"),
        "documents",
        "deleted_at IS NULL OR shared_with_client_at IS NULL",
    )
    op.create_check_constraint(
        op.f("ck_documents_shared_needs_file"),
        "documents",
        "shared_with_client_at IS NULL OR storage_key IS NOT NULL",
    )


def downgrade() -> None:
    # Dropping the columns only withdraws sharing (the safe direction).
    op.drop_constraint(op.f("ck_documents_shared_needs_file"), "documents", type_="check")
    op.drop_constraint(op.f("ck_documents_deleted_never_shared"), "documents", type_="check")
    op.drop_constraint(op.f("ck_documents_shared_by_needs_shared_at"), "documents", type_="check")
    op.drop_constraint(op.f("fk_documents_shared_by_id_users"), "documents", type_="foreignkey")
    op.drop_column("documents", "shared_by_id")
    op.drop_column("documents", "shared_with_client_at")
