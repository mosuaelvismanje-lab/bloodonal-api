"""Merge multiple heads

Revision ID: 9e81c3c4d579
Revises: 88f814a3bc17, add_call_sessions_20251201, add_notifications_table_20251201
Create Date: 2025-12-02 11:41:05.443290

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e81c3c4d579'
down_revision: Union[str, Sequence[str], None] = ('88f814a3bc17', 'add_call_sessions_20251201', 'add_notifications_table_20251201')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
