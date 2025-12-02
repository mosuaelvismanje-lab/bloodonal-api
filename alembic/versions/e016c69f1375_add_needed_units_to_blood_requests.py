"""Add needed_units to blood_requests

Revision ID: e016c69f1375
Revises: 82c133374cb1
Create Date: 2025-06-29 11:27:11.953690
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e016c69f1375'
down_revision: Union[str, Sequence[str], None] = '82c133374cb1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    This migration was already applied manually before Alembic ran it.
    The tables chat_rooms/messages and the column needed_units already exist.
    Therefore we intentionally skip running any operations.
    """
    pass


def downgrade() -> None:
    """
    No downgrade available because upgrade was skipped.
    """
    pass
