"""Judgment provenance and import runs (Batch 2): two new tables, nothing else changes.

``judgment_provenance`` holds, per judgment, the source's own record
identifiers, the neutral citation, the dataset snapshot and the attribution
to show (from ``lexflow-judgments/2`` manifests). ``judgment_import_runs``
records each importer run: counts and every item that was not imported, with
its reason. No existing table, column or row changes, so the upgrade cannot
lose or rewrite data, and an application at 0012 or 0013 keeps working.

The downgrade drops both tables. It is for development only.

Revision ID: 0014
Revises: 0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "judgment_provenance",
        sa.Column("judgment_id", sa.Uuid(), nullable=False),
        sa.Column("neutral_citation", sa.Text(), nullable=True),
        sa.Column("source_record", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("dataset", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("attribution", sa.Text(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "neutral_citation IS NULL OR char_length(neutral_citation) BETWEEN 1 AND 100",
            name=op.f("ck_judgment_provenance_neutral_citation_length"),
        ),
        sa.CheckConstraint(
            "attribution IS NULL OR char_length(attribution) BETWEEN 1 AND 1000",
            name=op.f("ck_judgment_provenance_attribution_length"),
        ),
        sa.ForeignKeyConstraint(
            ["judgment_id"],
            ["judgments.id"],
            name=op.f("fk_judgment_provenance_judgment_id_judgments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("judgment_id", name=op.f("pk_judgment_provenance")),
    )
    op.create_table(
        "judgment_import_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_key", sa.Text(), nullable=False),
        sa.Column("manifest_format", sa.Text(), nullable=False),
        sa.Column("manifest_sha256", sa.Text(), nullable=False),
        sa.Column("operator", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("counts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "manifest_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_judgment_import_runs_manifest_sha256_format"),
        ),
        sa.CheckConstraint(
            "char_length(source_key) BETWEEN 1 AND 63",
            name=op.f("ck_judgment_import_runs_source_key_length"),
        ),
        sa.CheckConstraint(
            "char_length(operator) BETWEEN 1 AND 200",
            name=op.f("ck_judgment_import_runs_operator_length"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_judgment_import_runs")),
    )
    op.create_index(
        "ix_judgment_import_runs_source_key_started_at",
        "judgment_import_runs",
        ["source_key", "started_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_judgment_import_runs_source_key_started_at", table_name="judgment_import_runs"
    )
    op.drop_table("judgment_import_runs")
    op.drop_table("judgment_provenance")
