"""Add loyalty_cards to user_profiles

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-03-16

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column(
            "loyalty_cards",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='{"countdown": true, "new_world": true, "paknsave": true}',
        ),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "loyalty_cards")
