"""Add city to healthcare_providers

Revision ID: ab0e4e80adc4
Revises: 4e9fc9e07bc5
Create Date: 2025-06-27 03:41:16.643207
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ab0e4e80adc4'
down_revision = '4e9fc9e07bc5'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # only add the new column, don't drop anything else
    op.add_column(
        'healthcare_providers',
        sa.Column('city', sa.String(), nullable=True)
    )

def downgrade() -> None:
    # remove it on downgrade
    op.drop_column('healthcare_providers', 'city')
