"""Add share_token columns for trolley/recipe sharing

Revision ID: g6a7b8c9d0e1
Revises: f5a6b7c8d9e0
Create Date: 2026-03-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("saved_trolleys", sa.Column("share_token", sa.String(32), nullable=True))
    op.create_unique_constraint("uq_saved_trolleys_share_token", "saved_trolleys", ["share_token"])

    op.add_column("recipes", sa.Column("share_token", sa.String(32), nullable=True))
    op.create_unique_constraint("uq_recipes_share_token", "recipes", ["share_token"])


def downgrade() -> None:
    op.drop_constraint("uq_recipes_share_token", "recipes", type_="unique")
    op.drop_column("recipes", "share_token")

    op.drop_constraint("uq_saved_trolleys_share_token", "saved_trolleys", type_="unique")
    op.drop_column("saved_trolleys", "share_token")
