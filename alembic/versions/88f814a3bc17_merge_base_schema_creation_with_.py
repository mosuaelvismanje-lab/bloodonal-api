"""Merge base schema creation with existing functional chain

Revision ID: 88f814a3bc17
Revises: 08a1d507803e, 5258e9c708d8
Create Date: 2025-12-01 08:49:07.161299

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '88f814a3bc17'
down_revision: Union[str, Sequence[str], None] = ('08a1d507803e', '5258e9c708d8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
