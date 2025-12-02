"""create notifications table

Revision ID: add_notifications_table_20251201
Revises: e016c69f1375
Create Date: 2025-12-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "add_notifications_table_20251201"
down_revision = "e016c69f1375"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("sub_type", sa.String(), nullable=False),
        sa.Column("location", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("timestamp", sa.BigInteger(), nullable=False),
        sa.Column(
            "read",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False
        ),
    )

    # Create index manually
    op.create_index(
        "ix_notifications_user_id",
        "notifications",
        ["user_id"]
    )


def downgrade():
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
