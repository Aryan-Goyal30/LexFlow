"""Judgment collection (Phase 4): sources, judgments, their text, chunks and vectors.

Only new tables; no existing table or row changes. Nothing is imported by the
migration: judgments arrive only through ``python -m lexflow.cli.judgments
import`` with a manifest that records the source and its terms of use.

- ``judgment_sources``: a source and the terms-of-use record for it
  (``is_synthetic`` marks invented test data).
- ``judgments``: metadata as supplied (citation, date and bench optional), a
  stable id derived from the source, the SHA-256 of the imported file.
- ``judgment_sections`` / ``judgment_chunks``: page-aware text as in Phase 3;
  chunks carry a generated ``tsvector`` with a GIN index for keyword search.
- ``judgment_chunk_embeddings``: optional 384-dimension vectors (pgvector).

The downgrade drops these tables and everything imported into them.

Revision ID: 0010
Revises: 0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "judgment_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("terms_url", sa.Text(), nullable=False),
        sa.Column("terms_checked_on", sa.Date(), nullable=False),
        sa.Column("terms_checked_by", sa.Text(), nullable=False),
        sa.Column("permitted_use", sa.Text(), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "key ~ '^[a-z0-9][a-z0-9-]{1,62}$'", name=op.f("ck_judgment_sources_key_format")
        ),
        sa.CheckConstraint(
            "terms_url ~ '^https://'", name=op.f("ck_judgment_sources_terms_url_https")
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 200", name=op.f("ck_judgment_sources_name_length")
        ),
        sa.CheckConstraint(
            "char_length(permitted_use) BETWEEN 1 AND 2000",
            name=op.f("ck_judgment_sources_permitted_use_length"),
        ),
        sa.CheckConstraint(
            "char_length(terms_checked_by) BETWEEN 1 AND 200",
            name=op.f("ck_judgment_sources_checked_by_length"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_judgment_sources")),
        sa.UniqueConstraint("key", name=op.f("uq_judgment_sources_key")),
    )
    op.create_table(
        "judgments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_document_id", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("court", sa.Text(), nullable=False),
        sa.Column("citation", sa.Text(), nullable=True),
        sa.Column("decision_date", sa.Date(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("bench", sa.Text(), nullable=True),
        sa.Column(
            "practice_areas", sa.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("extractor", sa.Text(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("section_count", sa.Integer(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("imported_by", sa.Text(), nullable=False),
        sa.Column("manifest_sha256", sa.Text(), nullable=False),
        sa.Column("index_status", sa.Text(), server_default=sa.text("'disabled'"), nullable=False),
        sa.Column("embedding_model", sa.Text(), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "content_sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_judgments_content_sha256_format")
        ),
        sa.CheckConstraint(
            "index_status IN ('disabled', 'pending', 'indexed', 'failed')",
            name=op.f("ck_judgments_index_status_valid"),
        ),
        sa.CheckConstraint("source_url ~ '^https://'", name=op.f("ck_judgments_source_url_https")),
        sa.CheckConstraint(
            "char_length(court) BETWEEN 1 AND 200", name=op.f("ck_judgments_court_length")
        ),
        sa.CheckConstraint(
            "char_length(source_document_id) BETWEEN 1 AND 200",
            name=op.f("ck_judgments_source_document_id_length"),
        ),
        sa.CheckConstraint(
            "char_length(title) BETWEEN 1 AND 500", name=op.f("ck_judgments_title_length")
        ),
        sa.CheckConstraint(
            "citation IS NULL OR char_length(citation) BETWEEN 1 AND 200",
            name=op.f("ck_judgments_citation_length"),
        ),
        sa.CheckConstraint(
            "decision_date IS NULL OR year = EXTRACT(YEAR FROM decision_date)",
            name=op.f("ck_judgments_year_matches_date"),
        ),
        sa.CheckConstraint(
            "year IS NULL OR year BETWEEN 1800 AND 2100", name=op.f("ck_judgments_year_range")
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["judgment_sources.id"],
            name=op.f("fk_judgments_source_id_judgment_sources"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_judgments")),
        sa.UniqueConstraint("content_sha256", name=op.f("uq_judgments_content_sha256")),
        sa.UniqueConstraint(
            "source_id",
            "source_document_id",
            name=op.f("uq_judgments_source_id_source_document_id"),
        ),
    )
    op.create_index("ix_judgments_court_year", "judgments", ["court", "year"], unique=False)
    op.create_index(
        "uq_judgments_citation",
        "judgments",
        [sa.literal_column("lower(citation)")],
        unique=True,
        postgresql_where=sa.text("citation IS NOT NULL"),
    )
    op.create_table(
        "judgment_sections",
        sa.Column("judgment_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.CheckConstraint("number >= 1", name=op.f("ck_judgment_sections_number_positive")),
        sa.CheckConstraint(
            "page_number IS NULL OR page_number >= 1",
            name=op.f("ck_judgment_sections_page_number_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["judgment_id"],
            ["judgments.id"],
            name=op.f("fk_judgment_sections_judgment_id_judgments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("judgment_id", "number", name=op.f("pk_judgment_sections")),
    )
    op.create_table(
        "judgment_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("judgment_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("section_number", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.Text(), nullable=False),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english'::regconfig, text)", persisted=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "content_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_judgment_chunks_content_sha256_format"),
        ),
        sa.CheckConstraint(
            "char_length(text) = char_end - char_start",
            name=op.f("ck_judgment_chunks_text_matches_offsets"),
        ),
        sa.CheckConstraint(
            "char_start >= 0 AND char_end > char_start",
            name=op.f("ck_judgment_chunks_offsets_valid"),
        ),
        sa.CheckConstraint("number >= 1", name=op.f("ck_judgment_chunks_number_positive")),
        sa.ForeignKeyConstraint(
            ["judgment_id", "section_number"],
            ["judgment_sections.judgment_id", "judgment_sections.number"],
            name=op.f("fk_judgment_chunks_judgment_id_judgment_sections"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["judgment_id"],
            ["judgments.id"],
            name=op.f("fk_judgment_chunks_judgment_id_judgments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_judgment_chunks")),
        sa.UniqueConstraint(
            "judgment_id", "number", name=op.f("uq_judgment_chunks_judgment_id_number")
        ),
    )
    op.create_index(
        "ix_judgment_chunks_search_vector",
        "judgment_chunks",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_table(
        "judgment_chunk_embeddings",
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("judgment_id", sa.Uuid(), nullable=False),
        sa.Column("content_sha256", sa.Text(), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "content_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_judgment_chunk_embeddings_content_sha256_format"),
        ),
        sa.CheckConstraint(
            "char_length(model) BETWEEN 1 AND 200",
            name=op.f("ck_judgment_chunk_embeddings_model_length"),
        ),
        sa.CheckConstraint(
            "dimensions = vector_dims(embedding)",
            name=op.f("ck_judgment_chunk_embeddings_dimensions_match"),
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["judgment_chunks.id"],
            name=op.f("fk_judgment_chunk_embeddings_chunk_id_judgment_chunks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["judgment_id"],
            ["judgments.id"],
            name=op.f("fk_judgment_chunk_embeddings_judgment_id_judgments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("chunk_id", "model", name=op.f("pk_judgment_chunk_embeddings")),
    )
    op.create_index(
        "ix_judgment_chunk_embeddings_judgment_id_model",
        "judgment_chunk_embeddings",
        ["judgment_id", "model"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_judgment_chunk_embeddings_judgment_id_model", table_name="judgment_chunk_embeddings"
    )
    op.drop_table("judgment_chunk_embeddings")
    op.drop_index(
        "ix_judgment_chunks_search_vector", table_name="judgment_chunks", postgresql_using="gin"
    )
    op.drop_table("judgment_chunks")
    op.drop_table("judgment_sections")
    op.drop_index(
        "uq_judgments_citation",
        table_name="judgments",
        postgresql_where=sa.text("citation IS NOT NULL"),
    )
    op.drop_index("ix_judgments_court_year", table_name="judgments")
    op.drop_table("judgments")
    op.drop_table("judgment_sources")
