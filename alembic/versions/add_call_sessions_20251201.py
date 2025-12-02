"""create call_sessions table

Revision ID: add_call_sessions_20251201
Revises: e016c69f1375
Create Date: 2025-12-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Correct revision IDs
revision = "add_call_sessions_20251201"
down_revision = "e016c69f1375"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "call_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("room_name", sa.String(length=255), nullable=False),
        sa.Column("caller_id", sa.String(length=128), nullable=False),
        sa.Column("callee_ids", postgresql.JSONB, nullable=True),
        sa.Column("callee_type", sa.String(length=64), nullable=True),
        sa.Column(
            "call_mode",
            sa.Enum("voice", "video", name="callmodeenum"),
            nullable=False,
        ),
        sa.Column("token", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "active",
                "ended",
                "missed",
                "cancelled",
                name="callstatusenum"
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # indexed session_id
    op.create_index(
        op.f("ix_call_sessions_session_id"),
        "call_sessions",
        ["session_id"],
        unique=True,
    )


def downgrade():
    op.drop_index(
        op.f("ix_call_sessions_session_id"),
        table_name="call_sessions",
    )
    op.drop_table("call_sessions")

    # Drop Postgres ENUM types
    op.execute("DROP TYPE IF EXISTS callmodeenum")
    op.execute("DROP TYPE IF EXISTS callstatusenum")
