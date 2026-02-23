"""merge heads

Revision ID: 79a4acac15c8
Revises: e2f3a4b5c6d7, f1a2b3c4d5e6
Create Date: 2026-02-23 13:32:26.121996

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '79a4acac15c8'
down_revision: Union[str, Sequence[str], None] = ('e2f3a4b5c6d7', 'f1a2b3c4d5e6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
