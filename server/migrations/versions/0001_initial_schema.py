"""Initial Phase 1 schema.

Users (advocates, no credentials), clients, cases, hearings, timeline events,
documents and per-year case-number counters. Rows that hold fictional sample
data carry ``is_sample = true``. ``timeline_events.actor_id`` is NULL when no
signed-in user made the change (always, in Phase 1).

Revision ID: 0001
Revises:
Create Date: 2026-10-19 05:37:45.047581
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "case_number_counters",
        sa.Column("year", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "last_value >= 0", name=op.f("ck_case_number_counters_last_value_non_negative")
        ),
        sa.CheckConstraint(
            "year BETWEEN 2000 AND 9999", name=op.f("ck_case_number_counters_year_range")
        ),
        sa.PrimaryKeyConstraint("year", name=op.f("pk_case_number_counters")),
    )
    op.create_table(
        "clients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("company", sa.Text(), nullable=True),
        sa.Column("is_sample", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("char_length(btrim(name)) > 0", name=op.f("ck_clients_name_not_blank")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clients")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("is_sample", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('Administrator', 'Advocate', 'Paralegal', 'Client')",
            name=op.f("ck_users_role_valid"),
        ),
        sa.CheckConstraint("char_length(btrim(name)) > 0", name=op.f("ck_users_name_not_blank")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(
        "uq_users_lower_email", "users", [sa.literal_column("lower(email)")], unique=True
    )
    op.create_table(
        "cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_number", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("priority", sa.Text(), nullable=False),
        sa.Column("practice_area", sa.Text(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("lead_advocate_id", sa.Uuid(), nullable=False),
        sa.Column("court_name", sa.Text(), nullable=True),
        sa.Column("opposing_party", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("opened_on", sa.Date(), nullable=False),
        sa.Column("is_sample", sa.Boolean(), server_default=sa.text("false"), nullable=False),
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
            "case_number ~ '^LF-[0-9]{4}-[0-9]{4,}$'", name=op.f("ck_cases_case_number_format")
        ),
        sa.CheckConstraint(
            "practice_area IN ('Corporate / Commercial', 'Civil', 'Criminal', 'Family', 'Intellectual Property', 'Constitutional / Administrative', 'Real Estate', 'Employment & Labour')",
            name=op.f("ck_cases_practice_area_valid"),
        ),
        sa.CheckConstraint(
            "priority IN ('Low', 'Medium', 'High', 'Critical')",
            name=op.f("ck_cases_priority_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('Open', 'In Progress', 'On Hold', 'Closed')",
            name=op.f("ck_cases_status_valid"),
        ),
        sa.CheckConstraint(
            "char_length(btrim(description)) >= 10", name=op.f("ck_cases_description_length")
        ),
        sa.CheckConstraint(
            "char_length(btrim(title)) BETWEEN 4 AND 300", name=op.f("ck_cases_title_length")
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name=op.f("fk_cases_client_id_clients"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["lead_advocate_id"],
            ["users.id"],
            name=op.f("fk_cases_lead_advocate_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cases")),
        sa.UniqueConstraint("case_number", name=op.f("uq_cases_case_number")),
    )
    op.create_index(op.f("ix_cases_client_id"), "cases", ["client_id"], unique=False)
    op.create_index(op.f("ix_cases_lead_advocate_id"), "cases", ["lead_advocate_id"], unique=False)
    op.create_index(op.f("ix_cases_opened_on"), "cases", ["opened_on"], unique=False)
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("document_type", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("size_label", sa.Text(), nullable=True),
        sa.Column("sha256", sa.Text(), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("uploaded_on", sa.Date(), nullable=False),
        sa.Column("is_sample", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_documents_sha256_format")
        ),
        sa.CheckConstraint(
            "storage_key IS NULL OR storage_key ~ '^[0-9a-f]{32}$'",
            name=op.f("ck_documents_storage_key_format"),
        ),
        sa.CheckConstraint(
            "(storage_key IS NULL AND sha256 IS NULL AND content_type IS NULL) OR (storage_key IS NOT NULL AND sha256 IS NOT NULL AND content_type IS NOT NULL AND size_bytes IS NOT NULL)",
            name=op.f("ck_documents_stored_file_complete"),
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255", name=op.f("ck_documents_name_length")
        ),
        sa.CheckConstraint(
            "size_bytes IS NOT NULL OR size_label IS NOT NULL", name=op.f("ck_documents_has_size")
        ),
        sa.CheckConstraint(
            "size_bytes IS NULL OR size_bytes > 0", name=op.f("ck_documents_size_bytes_positive")
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], name=op.f("fk_documents_case_id_cases"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_documents_storage_key")),
    )
    op.create_index(
        "uq_documents_case_id_lower_name",
        "documents",
        ["case_id", sa.literal_column("lower(name)")],
        unique=True,
    )
    op.create_table(
        "hearings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("hearing_date", sa.Date(), nullable=False),
        sa.Column("hearing_time", sa.Time(), nullable=True),
        sa.Column("court", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("is_sample", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["cases.id"], name=op.f("fk_hearings_case_id_cases"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hearings")),
    )
    op.create_index(
        "ix_hearings_case_id_hearing_date", "hearings", ["case_id", "hearing_date"], unique=False
    )
    op.create_table(
        "timeline_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("is_sample", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_timeline_events_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
            name=op.f("fk_timeline_events_case_id_cases"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_timeline_events")),
    )
    op.create_index(
        "ix_timeline_events_case_id_event_date",
        "timeline_events",
        ["case_id", "event_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_timeline_events_case_id_event_date", table_name="timeline_events")
    op.drop_table("timeline_events")
    op.drop_index("ix_hearings_case_id_hearing_date", table_name="hearings")
    op.drop_table("hearings")
    op.drop_index("uq_documents_case_id_lower_name", table_name="documents")
    op.drop_table("documents")
    op.drop_index(op.f("ix_cases_opened_on"), table_name="cases")
    op.drop_index(op.f("ix_cases_lead_advocate_id"), table_name="cases")
    op.drop_index(op.f("ix_cases_client_id"), table_name="cases")
    op.drop_table("cases")
    op.drop_index("uq_users_lower_email", table_name="users")
    op.drop_table("users")
    op.drop_table("clients")
    op.drop_table("case_number_counters")
