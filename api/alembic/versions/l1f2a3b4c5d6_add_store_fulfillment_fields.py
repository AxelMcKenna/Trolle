"""Add store fulfillment fields (delivery, click_collect, fees)

Revision ID: l1f2a3b4c5d6
Revises: k0e1f2a3b4c5
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "l1f2a3b4c5d6"
down_revision = "k0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("click_collect", sa.Boolean, nullable=True))
    op.add_column("stores", sa.Column("delivery", sa.Boolean, nullable=True))
    op.add_column("stores", sa.Column("delivery_fee_nzd", sa.Float, nullable=True))
    op.add_column("stores", sa.Column("min_order_nzd", sa.Float, nullable=True))
    op.add_column("stores", sa.Column("cc_fee_nzd", sa.Float, nullable=True))
    op.add_column("stores", sa.Column("free_delivery_threshold_nzd", sa.Float, nullable=True))
    op.add_column("stores", sa.Column("fulfillment_updated_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_store_fulfillment", "stores", ["chain", "delivery", "click_collect"])


def downgrade() -> None:
    op.drop_index("ix_store_fulfillment", table_name="stores")
    op.drop_column("stores", "fulfillment_updated_at")
    op.drop_column("stores", "free_delivery_threshold_nzd")
    op.drop_column("stores", "cc_fee_nzd")
    op.drop_column("stores", "min_order_nzd")
    op.drop_column("stores", "delivery_fee_nzd")
    op.drop_column("stores", "delivery")
    op.drop_column("stores", "click_collect")
