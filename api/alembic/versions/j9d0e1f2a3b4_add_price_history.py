"""Add price_history table for tracking price changes over time

Revision ID: j9d0e1f2a3b4
Revises: i8c9d0e1f2a3
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "j9d0e1f2a3b4"
down_revision = "i8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "price_history",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("price_nzd", sa.Float, nullable=False),
        sa.Column("promo_price_nzd", sa.Float, nullable=True),
        sa.Column("is_member_only", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_index(
        "ix_price_history_product_store_recorded",
        "price_history",
        ["product_id", "store_id", "recorded_at"],
    )
    op.create_index(
        "ix_price_history_recorded_at",
        "price_history",
        ["recorded_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_price_history_recorded_at", table_name="price_history")
    op.drop_index("ix_price_history_product_store_recorded", table_name="price_history")
    op.drop_table("price_history")
