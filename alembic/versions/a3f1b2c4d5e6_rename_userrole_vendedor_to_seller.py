"""rename userrole vendedor to seller

Revision ID: a3f1b2c4d5e6
Revises: 9ff0c087de3b
Create Date: 2026-06-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a3f1b2c4d5e6'
down_revision: Union[str, Sequence[str], None] = '9ff0c087de3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename the 'vendedor' enum value to 'seller' in the userrole type."""
    op.execute("ALTER TYPE userrole RENAME VALUE 'vendedor' TO 'seller'")


def downgrade() -> None:
    """Revert 'seller' back to 'vendedor' in the userrole type."""
    op.execute("ALTER TYPE userrole RENAME VALUE 'seller' TO 'vendedor'")
