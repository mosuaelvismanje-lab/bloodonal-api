from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5cac4be2f931'
down_revision: Union[str, Sequence[str], None] = 'ab0e4e80adc4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema.

    NOTE: The column 'city' on 'blood_requests' was already created in the database
    during the application of the manual base migration.
    This function is set to 'pass' to avoid the DuplicateColumn error and synchronize
    the Alembic history with the current database schema.
    """
    pass


def downgrade() -> None:
    """Downgrade schema: Remove 'city' column from blood_requests."""
    # This remains functional in case you need to roll back history later.
    op.drop_column('blood_requests', 'city')
