"""Accounts, sessions and the audit log (Phase 2).

- ``users`` gains sign-in fields (Argon2id hash, active flag, temporary-password
  and lockout state) and ``client_id``, the client record a Client user
  represents. Several users may represent one client. Existing rows keep
  working: they have no password (cannot sign in) and are active.
- ``sessions`` stores the SHA-256 of each session token, never the token.
- ``audit_events`` is append-only: a row trigger rejects UPDATE and DELETE.
  This protects against application bugs, not against someone with the
  database owner's credentials (who can disable triggers or TRUNCATE).

Downgrading drops sessions and the audit history (development use only).

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPEND_ONLY_FUNCTION = """
CREATE FUNCTION lexflow_audit_events_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only: % is not allowed', TG_OP
        USING ERRCODE = 'restrict_violation';
END;
$$
"""

APPEND_ONLY_TRIGGER = """
CREATE TRIGGER audit_events_append_only
BEFORE UPDATE OR DELETE ON audit_events
FOR EACH ROW EXECUTE FUNCTION lexflow_audit_events_append_only()
"""


def upgrade() -> None:
    # --- users: sign-in fields --------------------------------------------------
    op.add_column("users", sa.Column("client_id", sa.Uuid(), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "users", sa.Column("temp_password_expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column("failed_login_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        op.f("fk_users_client_id_clients"),
        "users",
        "clients",
        ["client_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_users_client_id"), "users", ["client_id"], unique=False)
    op.create_check_constraint(
        op.f("ck_users_client_link"), "users", "(role = 'Client') = (client_id IS NOT NULL)"
    )
    op.create_check_constraint(
        op.f("ck_users_login_needs_email"), "users", "password_hash IS NULL OR email IS NOT NULL"
    )
    op.create_check_constraint(
        op.f("ck_users_failed_login_count_non_negative"), "users", "failed_login_count >= 0"
    )

    # --- sessions ----------------------------------------------------------------
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "token_hash ~ '^[0-9a-f]{64}$'", name=op.f("ck_sessions_token_hash_format")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sessions_token_hash")),
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)

    # --- audit_events (append-only) ---------------------------------------------
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_name", sa.Text(), nullable=True),
        sa.Column("actor_role", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=True),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("case_id", sa.Uuid(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "outcome IN ('success', 'denied', 'failed')",
            name=op.f("ck_audit_events_outcome_valid"),
        ),
        sa.CheckConstraint(
            "char_length(action) > 0", name=op.f("ck_audit_events_action_not_blank")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(op.f("ix_audit_events_action"), "audit_events", ["action"], unique=False)
    op.create_index(op.f("ix_audit_events_actor_id"), "audit_events", ["actor_id"], unique=False)
    op.create_index(op.f("ix_audit_events_case_id"), "audit_events", ["case_id"], unique=False)
    op.create_index(
        op.f("ix_audit_events_occurred_at"), "audit_events", ["occurred_at"], unique=False
    )
    op.execute(APPEND_ONLY_FUNCTION)
    op.execute(APPEND_ONLY_TRIGGER)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_events_append_only ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS lexflow_audit_events_append_only()")
    op.drop_index(op.f("ix_audit_events_occurred_at"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_case_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_actor_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_action"), table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_table("sessions")

    op.drop_constraint(op.f("ck_users_failed_login_count_non_negative"), "users", type_="check")
    op.drop_constraint(op.f("ck_users_login_needs_email"), "users", type_="check")
    op.drop_constraint(op.f("ck_users_client_link"), "users", type_="check")
    op.drop_index(op.f("ix_users_client_id"), table_name="users")
    op.drop_constraint(op.f("fk_users_client_id_clients"), "users", type_="foreignkey")
    for column in (
        "updated_at",
        "last_login_at",
        "locked_until",
        "failed_login_count",
        "temp_password_expires_at",
        "must_change_password",
        "is_active",
        "password_hash",
        "client_id",
    ):
        op.drop_column("users", column)
