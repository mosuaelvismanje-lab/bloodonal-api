"""Expand city and hospital columns

Revision ID: 3a8d0e640054
Revises: 39eca1b98c6c
Create Date: 2025-06-28 05:28:24.651612

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a8d0e640054'
down_revision: Union[str, Sequence[str], None] = '39eca1b98c6c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to expand city and hospital fields."""
    op.alter_column('blood_donors', 'city',
                    existing_type=sa.String(length=5),
                    type_=sa.String(length=100),
                    existing_nullable=False)

    op.alter_column('blood_donors', 'hospital',
                    existing_type=sa.String(length=5),
                    type_=sa.String(length=100),
                    existing_nullable=True)


def downgrade() -> None:
    """Downgrade schema to original city and hospital length."""
    op.alter_column('blood_donors', 'city',
                    existing_type=sa.String(length=100),
                    type_=sa.String(length=5),
                    existing_nullable=False)

    op.alter_column('blood_donors', 'hospital',
                    existing_type=sa.String(length=100),
                    type_=sa.String(length=5),
                    existing_nullable=True)
