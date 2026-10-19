"""Hearings can be cancelled (kept, never deleted) and record who scheduled them (Phase 2).

A cancelled hearing stays on the case with the reason, but no longer counts
as the next hearing or appears among upcoming hearings.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "hearings",
        sa.Column("status", sa.Text(), server_default=sa.text("'Scheduled'"), nullable=False),
    )
    op.add_column("hearings", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("hearings", sa.Column("cancelled_by_id", sa.Uuid(), nullable=True))
    op.add_column("hearings", sa.Column("cancellation_reason", sa.Text(), nullable=True))
    op.add_column("hearings", sa.Column("created_by_id", sa.Uuid(), nullable=True))
    op.add_column(
        "hearings",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        op.f("fk_hearings_cancelled_by_id_users"),
        "hearings",
        "users",
        ["cancelled_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_hearings_created_by_id_users"),
        "hearings",
        "users",
        ["created_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        op.f("ck_hearings_status_valid"), "hearings", "status IN ('Scheduled', 'Cancelled')"
    )
    op.create_check_constraint(
        op.f("ck_hearings_cancelled_at_matches_status"),
        "hearings",
        "(status = 'Cancelled') = (cancelled_at IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_hearings_cancellation_reason_length"),
        "hearings",
        "cancellation_reason IS NULL OR char_length(cancellation_reason) BETWEEN 1 AND 500",
    )


def downgrade() -> None:
    # Dropping the status would turn cancelled hearings back into scheduled
    # ones: refuse rather than misrepresent them.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM hearings WHERE status = 'Cancelled') THEN
            RAISE EXCEPTION 'cancelled hearings exist; downgrading would show them as '
              'scheduled. Remove them deliberately first if that is really wanted';
          END IF;
        END $$;
        """
    )
    op.drop_constraint(op.f("ck_hearings_cancellation_reason_length"), "hearings", type_="check")
    op.drop_constraint(op.f("ck_hearings_cancelled_at_matches_status"), "hearings", type_="check")
    op.drop_constraint(op.f("ck_hearings_status_valid"), "hearings", type_="check")
    op.drop_constraint(op.f("fk_hearings_created_by_id_users"), "hearings", type_="foreignkey")
    op.drop_constraint(op.f("fk_hearings_cancelled_by_id_users"), "hearings", type_="foreignkey")
    op.drop_column("hearings", "updated_at")
    op.drop_column("hearings", "created_by_id")
    op.drop_column("hearings", "cancellation_reason")
    op.drop_column("hearings", "cancelled_by_id")
    op.drop_column("hearings", "cancelled_at")
    op.drop_column("hearings", "status")
