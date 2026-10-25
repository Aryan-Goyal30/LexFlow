"""Outcome assessments (Phase 7, synthetic engineering demo): three new tables.

``outcome_assessments`` holds each assessment of a reviewed analysis run,
written once and never changed. ``outcome_assessment_reviews`` holds a
lawyer's current decision on one assessment (unique per assessment), and
``outcome_assessment_review_events`` the append-only history of every change
(unique per review and version). No existing table, column or row changes, so
the upgrade cannot lose or rewrite data.

The feature stays off unless ``LEXFLOW_OUTCOME_ASSESSMENT=true``, which the
settings allow only with a test or e2e database. The downgrade drops the three
tables and everything in them; it is for development only.

Revision ID: 0013
Revises: 0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _review_checks(table: str) -> list[sa.CheckConstraint]:
    return [
        sa.CheckConstraint(
            "status IN ('unreviewed', 'accepted', 'edited', 'rejected')",
            name=op.f(f"ck_{table}_status_valid"),
        ),
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
        "outcome_assessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("inputs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("removed", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('ready', 'insufficient', 'failed')",
            name=op.f("ck_outcome_assessments_status_valid"),
        ),
        sa.CheckConstraint(
            "(status = 'ready') = (result IS NOT NULL)",
            name=op.f("ck_outcome_assessments_result_matches_status"),
        ),
        sa.CheckConstraint(
            "(status = 'ready') = (reason_code IS NULL)",
            name=op.f("ck_outcome_assessments_reason_matches_status"),
        ),
        sa.CheckConstraint(
            "reason IS NULL OR char_length(reason) <= 500",
            name=op.f("ck_outcome_assessments_reason_length"),
        ),
        sa.CheckConstraint(
            "char_length(provider) BETWEEN 1 AND 50",
            name=op.f("ck_outcome_assessments_provider_length"),
        ),
        sa.CheckConstraint(
            "char_length(model) BETWEEN 1 AND 100", name=op.f("ck_outcome_assessments_model_length")
        ),
        sa.CheckConstraint(
            "char_length(prompt_version) BETWEEN 1 AND 50",
            name=op.f("ck_outcome_assessments_prompt_version_length"),
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
            name=op.f("fk_outcome_assessments_case_id_cases"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_id"],
            ["users.id"],
            name=op.f("fk_outcome_assessments_requested_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["analysis_runs.id"],
            name=op.f("fk_outcome_assessments_run_id_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outcome_assessments")),
    )
    op.create_index(
        "ix_outcome_assessments_run_id_created_at",
        "outcome_assessments",
        ["run_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_outcome_assessments_requested_by_id_created_at",
        "outcome_assessments",
        ["requested_by_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "outcome_assessment_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
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
        *_review_checks("outcome_assessment_reviews"),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["outcome_assessments.id"],
            name=op.f("fk_outcome_assessment_reviews_assessment_id_outcome_assessments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
            name=op.f("fk_outcome_assessment_reviews_case_id_cases"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_id"],
            ["users.id"],
            name=op.f("fk_outcome_assessment_reviews_reviewed_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outcome_assessment_reviews")),
        sa.UniqueConstraint(
            "assessment_id", name=op.f("uq_outcome_assessment_reviews_assessment_id")
        ),
    )
    op.create_index(
        "ix_outcome_assessment_reviews_case_id",
        "outcome_assessment_reviews",
        ["case_id"],
        unique=False,
    )
    op.create_table(
        "outcome_assessment_review_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
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
        *_review_checks("outcome_assessment_review_events"),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_outcome_assessment_review_events_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["outcome_assessments.id"],
            name="fk_outcome_assessment_review_events_assessment_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
            name=op.f("fk_outcome_assessment_review_events_case_id_cases"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["outcome_assessment_reviews.id"],
            name="fk_outcome_assessment_review_events_review_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outcome_assessment_review_events")),
        sa.UniqueConstraint(
            "review_id",
            "version",
            name=op.f("uq_outcome_assessment_review_events_review_id_version"),
        ),
    )
    op.create_index(
        "ix_outcome_assessment_review_events_assessment_id",
        "outcome_assessment_review_events",
        ["assessment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_outcome_assessment_review_events_assessment_id",
        table_name="outcome_assessment_review_events",
    )
    op.drop_table("outcome_assessment_review_events")
    op.drop_index("ix_outcome_assessment_reviews_case_id", table_name="outcome_assessment_reviews")
    op.drop_table("outcome_assessment_reviews")
    op.drop_index(
        "ix_outcome_assessments_requested_by_id_created_at", table_name="outcome_assessments"
    )
    op.drop_index("ix_outcome_assessments_run_id_created_at", table_name="outcome_assessments")
    op.drop_table("outcome_assessments")
