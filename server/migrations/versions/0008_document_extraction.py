"""Document text extraction (Phase 3): jobs, extracted text, chunks.

Only new tables; no existing table or row changes. Documents uploaded before
this migration get no job: they are queued explicitly with
``python -m lexflow.cli.documents queue-extraction``.

- ``document_extractions``: one job per stored document (status, reason,
  attempts, the worker's lease) and the outcome (counts, index status).
- ``document_sections``: the extracted text of each PDF page, or each numbered
  part of a document without pages; ``page_number`` is null then.
- ``document_chunks``: passages of a section with exact character offsets and
  a SHA-256 of their text.

Everything here is derived from the stored files and is removed with the
document (``ON DELETE CASCADE``). The downgrade drops it; it can be rebuilt by
processing the documents again.

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_extractions",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "queued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.Text(), nullable=True),
        sa.Column("requested_by_id", sa.Uuid(), nullable=True),
        sa.Column("extractor", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("section_count", sa.Integer(), nullable=True),
        sa.Column("char_count", sa.Integer(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("index_status", sa.Text(), server_default=sa.text("'disabled'"), nullable=False),
        sa.Column("index_reason", sa.Text(), nullable=True),
        sa.Column("embedding_model", sa.Text(), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'ready', 'failed', 'unsupported')",
            name=op.f("ck_document_extractions_status_valid"),
        ),
        sa.CheckConstraint(
            "index_status IN ('disabled', 'pending', 'indexed', 'failed')",
            name=op.f("ck_document_extractions_index_status_valid"),
        ),
        sa.CheckConstraint(
            "(status IN ('failed', 'unsupported')) = (reason_code IS NOT NULL)",
            name=op.f("ck_document_extractions_reason_matches_status"),
        ),
        sa.CheckConstraint(
            "reason IS NULL OR char_length(reason) <= 500",
            name=op.f("ck_document_extractions_reason_length"),
        ),
        sa.CheckConstraint(
            "(status = 'processing') = (lease_expires_at IS NOT NULL)",
            name=op.f("ck_document_extractions_lease_matches_status"),
        ),
        sa.CheckConstraint(
            "attempts >= 0", name=op.f("ck_document_extractions_attempts_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_extractions_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_id"],
            ["users.id"],
            name=op.f("fk_document_extractions_requested_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("document_id", name=op.f("pk_document_extractions")),
    )
    op.create_index(
        "ix_document_extractions_status_queued_at",
        "document_extractions",
        ["status", "queued_at"],
        unique=False,
    )

    op.create_table(
        "document_sections",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.CheckConstraint("number >= 1", name=op.f("ck_document_sections_number_positive")),
        sa.CheckConstraint(
            "page_number IS NULL OR page_number >= 1",
            name=op.f("ck_document_sections_page_number_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_sections_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("document_id", "number", name=op.f("pk_document_sections")),
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("section_number", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("number >= 1", name=op.f("ck_document_chunks_number_positive")),
        sa.CheckConstraint(
            "char_start >= 0 AND char_end > char_start",
            name=op.f("ck_document_chunks_offsets_valid"),
        ),
        sa.CheckConstraint(
            "char_length(text) = char_end - char_start",
            name=op.f("ck_document_chunks_text_matches_offsets"),
        ),
        sa.CheckConstraint(
            "content_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_document_chunks_content_sha256_format"),
        ),
        sa.CheckConstraint(
            "page_number IS NULL OR page_number >= 1",
            name=op.f("ck_document_chunks_page_number_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_chunks_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "section_number"],
            ["document_sections.document_id", "document_sections.number"],
            name=op.f("fk_document_chunks_document_id_document_sections"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_chunks")),
        sa.UniqueConstraint(
            "document_id", "number", name=op.f("uq_document_chunks_document_id_number")
        ),
    )
    op.create_index(
        "ix_document_chunks_document_id_section_number",
        "document_chunks",
        ["document_id", "section_number"],
        unique=False,
    )


def downgrade() -> None:
    # Derived data only: it can be rebuilt by processing the documents again.
    op.drop_index("ix_document_chunks_document_id_section_number", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_table("document_sections")
    op.drop_index("ix_document_extractions_status_queued_at", table_name="document_extractions")
    op.drop_table("document_extractions")
