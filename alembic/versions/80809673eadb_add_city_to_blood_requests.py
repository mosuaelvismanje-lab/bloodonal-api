from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '80809673eadb'
down_revision: Union[str, Sequence[str], None] = '42cf57dd7921'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema.

    NOTE: This migration failed due to attempts to drop indexes/tables
    that did not exist (UndefinedObject error) and duplicate column additions.
    The intended changes were already applied in a prior step.
    This function is set to 'pass' to synchronize Alembic history with the
    current database schema and resolve the failure.
    """
    pass


def downgrade() -> None:
    """Downgrade schema."""
    # Since the upgrade is set to pass, the downgrade is also set to pass
    # for simplicity, as we assume no complex rollbacks are needed.
    pass