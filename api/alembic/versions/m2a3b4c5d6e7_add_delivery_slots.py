"""Add delivery_slots table for tracking fulfillment slot availability

Revision ID: m2a3b4c5d6e7
Revises: l1f2a3b4c5d6
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "m2a3b4c5d6e7"
down_revision = "l1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delivery_slots",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("store_id", UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fulfillment_type", sa.String(16), nullable=False),
        sa.Column("slot_date", sa.Date, nullable=False),
        sa.Column("slot_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("slot_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_available", sa.Boolean, nullable=False),
        sa.Column("price_nzd", sa.Float, nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("store_id", "fulfillment_type", "slot_start", name="uq_delivery_slot"),
    )

    op.create_index("ix_delivery_slot_store_type_date", "delivery_slots", ["store_id", "fulfillment_type", "slot_date"])
    op.create_index("ix_delivery_slot_available", "delivery_slots", ["store_id", "fulfillment_type", "is_available"])


def downgrade() -> None:
    op.drop_index("ix_delivery_slot_available", table_name="delivery_slots")
    op.drop_index("ix_delivery_slot_store_type_date", table_name="delivery_slots")
    op.drop_table("delivery_slots")
