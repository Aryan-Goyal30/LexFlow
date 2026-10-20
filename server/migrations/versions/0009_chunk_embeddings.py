"""Chunk embeddings (pgvector): one 384-dimension vector per chunk and model.

Adds the ``vector`` extension (needs a PostgreSQL server with pgvector, such as
``pgvector/pgvector:pg17-trixie``; ADR 0016) and one new table. No existing
table or row changes; documents are indexed only when embeddings are enabled
and the worker (or ``python -m lexflow.cli.models queue-indexing``) asks.

- ``document_chunk_embeddings``: the vector of a chunk under a model and
  revision, with the chunk's SHA-256 at embedding time. Removed with the chunk
  or document (``ON DELETE CASCADE``).

Searches run per case over that case's chunks with an exact cosine distance,
so there is no approximate (HNSW) index yet.

The downgrade drops the table and the extension; the vectors can be rebuilt
from the stored chunks.

Revision ID: 0009
Revises: 0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "document_chunk_embeddings",
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
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
            "dimensions = vector_dims(embedding)",
            name=op.f("ck_document_chunk_embeddings_dimensions_match"),
        ),
        sa.CheckConstraint(
            "content_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_document_chunk_embeddings_content_sha256_format"),
        ),
        sa.CheckConstraint(
            "char_length(model) BETWEEN 1 AND 200",
            name=op.f("ck_document_chunk_embeddings_model_length"),
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["document_chunks.id"],
            name=op.f("fk_document_chunk_embeddings_chunk_id_document_chunks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_chunk_embeddings_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("chunk_id", "model", name=op.f("pk_document_chunk_embeddings")),
    )
    op.create_index(
        op.f("ix_document_chunk_embeddings_document_id_model"),
        "document_chunk_embeddings",
        ["document_id", "model"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_document_chunk_embeddings_document_id_model"),
        table_name="document_chunk_embeddings",
    )
    op.drop_table("document_chunk_embeddings")
    op.execute("DROP EXTENSION IF EXISTS vector")
