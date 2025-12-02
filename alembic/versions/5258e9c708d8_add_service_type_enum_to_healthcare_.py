"""add service_type enum to healthcare_providers

Revision ID: 5258e9c708d8
Revises: e016c69f1375
Create Date: 2025-10-26 10:57:39.299634
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5258e9c708d8'
down_revision: Union[str, Sequence[str], None] = 'e016c69f1375'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    This migration already exists in the database (enum + column already created),
    so we skip it to avoid duplicate-column and enum-exists errors.
    """
    pass


def downgrade() -> None:
    """
    No downgrade actions because the upgrade was skipped.
    """
    pass
