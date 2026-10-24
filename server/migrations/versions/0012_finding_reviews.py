"""Lawyer review of analysis findings (Phase 6): two new tables, nothing else changes.

``analysis_finding_reviews`` holds a lawyer's current decision on one finding
of one analysis run (unique per run and finding id); the run's stored result
is never changed. ``analysis_finding_review_events`` is the append-only
history of every change (unique per review and version). No existing table,
column or row changes, so the upgrade cannot lose or rewrite data.

The downgrade drops both tables and every recorded review decision. It is
for development only; take a backup first if reviews must be kept.

Revision ID: 0012
Revises: 0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KIND_MATCHES_ID = (
    "left(finding_id, 1) = CASE finding_kind WHEN 'fact' THEN 'F' WHEN 'issue' THEN 'I' "
    "WHEN 'precedent' THEN 'P' WHEN 'contradiction' THEN 'C' END"
)


def _checks(table: str) -> list[sa.CheckConstraint]:
    return [
        sa.CheckConstraint(
            "status IN ('unreviewed', 'accepted', 'edited', 'rejected')",
            name=op.f(f"ck_{table}_status_valid"),
        ),
        sa.CheckConstraint(
            "finding_kind IN ('fact', 'issue', 'precedent', 'contradiction')",
            name=op.f(f"ck_{table}_finding_kind_valid"),
        ),
        sa.CheckConstraint(
            "finding_id ~ '^[FIPC][1-9][0-9]{0,3}$'", name=op.f(f"ck_{table}_finding_id_format")
        ),
        sa.CheckConstraint(KIND_MATCHES_ID, name=op.f(f"ck_{table}_finding_kind_matches_id")),
        sa.CheckConstraint(
            "(status = 'edited') = (reviewed_text IS NOT NULL)",
            name=op.f(f"ck_{table}_text_matches_status"),
        ),
        sa.CheckConstraint(
            "reviewed_text IS NULL OR char_length(reviewed_text) BETWEEN 1 AND 2000",
            name=op.f(f"ck_{table}_reviewed_text_length"),
        ),
        sa.CheckConstraint(
            "note IS NULL OR char_length(note) BETWEEN 1 AND 2000",
            name=op.f(f"ck_{table}_note_length"),
        ),
        sa.CheckConstraint("version >= 1", name=op.f(f"ck_{table}_version_positive")),
    ]


def upgrade() -> None:
    op.create_table(
        "analysis_finding_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("finding_kind", sa.Text(), nullable=False),
        sa.Column("finding_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reviewed_text", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("reviewed_by_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        *_checks("analysis_finding_reviews"),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
            name=op.f("fk_analysis_finding_reviews_case_id_cases"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_id"],
            ["users.id"],
            name=op.f("fk_analysis_finding_reviews_reviewed_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["analysis_runs.id"],
            name=op.f("fk_analysis_finding_reviews_run_id_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_finding_reviews")),
        sa.UniqueConstraint(
            "run_id", "finding_id", name=op.f("uq_analysis_finding_reviews_run_id_finding_id")
        ),
    )
    op.create_index(
        "ix_analysis_finding_reviews_case_id",
        "analysis_finding_reviews",
        ["case_id"],
        unique=False,
    )
    op.create_table(
        "analysis_finding_review_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("finding_kind", sa.Text(), nullable=False),
        sa.Column("finding_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reviewed_text", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        *_checks("analysis_finding_review_events"),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_analysis_finding_review_events_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
            name=op.f("fk_analysis_finding_review_events_case_id_cases"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["analysis_finding_reviews.id"],
            name="fk_analysis_finding_review_events_review_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["analysis_runs.id"],
            name=op.f("fk_analysis_finding_review_events_run_id_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_finding_review_events")),
        sa.UniqueConstraint(
            "review_id", "version", name=op.f("uq_analysis_finding_review_events_review_id_version")
        ),
    )
    op.create_index(
        "ix_analysis_finding_review_events_case_id_occurred_at",
        "analysis_finding_review_events",
        ["case_id", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_analysis_finding_review_events_case_id_occurred_at",
        table_name="analysis_finding_review_events",
    )
    op.drop_table("analysis_finding_review_events")
    op.drop_index("ix_analysis_finding_reviews_case_id", table_name="analysis_finding_reviews")
    op.drop_table("analysis_finding_reviews")
