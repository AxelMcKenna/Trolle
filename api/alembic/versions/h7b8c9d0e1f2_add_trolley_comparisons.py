"""Add trolley_comparisons table for savings tracking

Revision ID: h7b8c9d0e1f2
Revises: g6a7b8c9d0e1
Create Date: 2026-03-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "h7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "g6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trolley_comparisons",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trolley_id", UUID(as_uuid=True), sa.ForeignKey("saved_trolleys.id", ondelete="SET NULL"), nullable=True),
        sa.Column("cheapest_store_name", sa.String(255), nullable=True),
        sa.Column("cheapest_total", sa.Float, nullable=False),
        sa.Column("most_expensive_total", sa.Float, nullable=False),
        sa.Column("savings", sa.Float, nullable=False),
        sa.Column("item_count", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_trolley_comparisons_user", "trolley_comparisons", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_trolley_comparisons_user")
    op.drop_table("trolley_comparisons")
