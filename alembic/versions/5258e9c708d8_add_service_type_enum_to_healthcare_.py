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
    """Upgrade schema."""
    # 1. Create the enum type
    service_type_enum = sa.Enum("doctor", "nurse", "lab", name="service_type_enum")
    service_type_enum.create(op.get_bind(), checkfirst=True)

    # 2. Add the column using the enum
    op.add_column(
        "healthcare_providers",
        sa.Column("service_type", service_type_enum, nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Drop the column first
    op.drop_column("healthcare_providers", "service_type")

    # 2. Drop the enum type
    service_type_enum = sa.Enum("doctor", "nurse", "lab", name="service_type_enum")
    service_type_enum.drop(op.get_bind(), checkfirst=True)
