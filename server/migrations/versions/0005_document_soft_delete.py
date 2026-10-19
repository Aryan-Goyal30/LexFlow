"""Documents are deleted softly, and record who uploaded them (Phase 2).

Deleting a document hides it and keeps its file, so the Administrator or the
lead advocate can restore it. Only the separate, guarded command
``python -m lexflow.cli.documents purge`` removes rows and files for good;
nothing purges automatically.

A document's name is unique per case among live documents only, so a name can
be reused after the old document was deleted.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("uploaded_by_id", sa.Uuid(), nullable=True))
    op.add_column("documents", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("deleted_by_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_documents_uploaded_by_id_users"),
        "documents",
        "users",
        ["uploaded_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_documents_deleted_by_id_users"),
        "documents",
        "users",
        ["deleted_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # Who deleted it is only known for a deleted document.
    op.create_check_constraint(
        op.f("ck_documents_deleted_by_needs_deleted_at"),
        "documents",
        "deleted_by_id IS NULL OR deleted_at IS NOT NULL",
    )
    op.drop_index("uq_documents_case_id_lower_name", table_name="documents")
    op.create_index(
        "uq_documents_case_id_lower_name",
        "documents",
        ["case_id", sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    # Deleted documents with the same name as a live one would break the old
    # index: refuse rather than drop data. Purge them first.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM documents
            GROUP BY case_id, lower(name) HAVING count(*) > 1
          ) THEN
            RAISE EXCEPTION 'deleted documents share a name with others on the same case; '
              'purge or rename them before downgrading';
          END IF;
        END $$;
        """
    )
    op.drop_index("uq_documents_case_id_lower_name", table_name="documents")
    op.create_index(
        "uq_documents_case_id_lower_name",
        "documents",
        ["case_id", sa.text("lower(name)")],
        unique=True,
    )
    op.drop_constraint(op.f("ck_documents_deleted_by_needs_deleted_at"), "documents", type_="check")
    op.drop_constraint(op.f("fk_documents_deleted_by_id_users"), "documents", type_="foreignkey")
    op.drop_constraint(op.f("fk_documents_uploaded_by_id_users"), "documents", type_="foreignkey")
    op.drop_column("documents", "deleted_by_id")
    op.drop_column("documents", "deleted_at")
    op.drop_column("documents", "uploaded_by_id")
