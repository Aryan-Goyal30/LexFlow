"""AI case analysis runs (Phase 5): one new table, nothing else changes.

``analysis_runs`` records each analysis: who asked, the provider, model and
prompt version, the selected documents and limits, the evidence references
sent (ids and content hashes, not text), the validated result, what
validation removed and the provider's token counts. A partial unique index
allows one waiting or running run per case. No existing table or row changes.

The downgrade drops the table and every stored run (runs can be made again).

Revision ID: 0011
Revises: 0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.Text(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("selection", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("removed", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(status = 'failed') = (reason_code IS NOT NULL)",
            name=op.f("ck_analysis_runs_reason_matches_status"),
        ),
        sa.CheckConstraint(
            "(status = 'ready') = (result IS NOT NULL)",
            name=op.f("ck_analysis_runs_result_matches_status"),
        ),
        sa.CheckConstraint(
            "(status = 'running') = (lease_expires_at IS NOT NULL)",
            name=op.f("ck_analysis_runs_lease_matches_status"),
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'ready', 'failed')",
            name=op.f("ck_analysis_runs_status_valid"),
        ),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_analysis_runs_attempts_non_negative")),
        sa.CheckConstraint(
            "char_length(model) BETWEEN 1 AND 100", name=op.f("ck_analysis_runs_model_length")
        ),
        sa.CheckConstraint(
            "char_length(prompt_version) BETWEEN 1 AND 50",
            name=op.f("ck_analysis_runs_prompt_version_length"),
        ),
        sa.CheckConstraint(
            "char_length(provider) BETWEEN 1 AND 50", name=op.f("ck_analysis_runs_provider_length")
        ),
        sa.CheckConstraint(
            "reason IS NULL OR char_length(reason) <= 500",
            name=op.f("ck_analysis_runs_reason_length"),
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
            name=op.f("fk_analysis_runs_case_id_cases"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_id"],
            ["users.id"],
            name=op.f("fk_analysis_runs_requested_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_runs")),
    )
    op.create_index(
        "ix_analysis_runs_case_id_created_at",
        "analysis_runs",
        ["case_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_analysis_runs_requested_by_id_created_at",
        "analysis_runs",
        ["requested_by_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_analysis_runs_status_available_at",
        "analysis_runs",
        ["status", "available_at"],
        unique=False,
    )
    op.create_index(
        "uq_analysis_runs_case_id_active",
        "analysis_runs",
        ["case_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_analysis_runs_case_id_active",
        table_name="analysis_runs",
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.drop_index("ix_analysis_runs_status_available_at", table_name="analysis_runs")
    op.drop_index("ix_analysis_runs_requested_by_id_created_at", table_name="analysis_runs")
    op.drop_index("ix_analysis_runs_case_id_created_at", table_name="analysis_runs")
    op.drop_table("analysis_runs")
