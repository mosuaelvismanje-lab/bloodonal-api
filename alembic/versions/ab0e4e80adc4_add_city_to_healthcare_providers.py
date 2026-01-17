from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ab0e4e80adc4'
down_revision: Union[str, Sequence[str], None] = '4e9fc9e07bc5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema. (Made a no-op as columns were added in the base revision 08a1d507803e)"""
    # This migration is now redundant and must be skipped.
    pass


def downgrade() -> None:
    """Downgrade schema. (Made a no-op as columns were added in the base revision 08a1d507803e)"""
    # This migration is now redundant and must be skipped.
    pass
