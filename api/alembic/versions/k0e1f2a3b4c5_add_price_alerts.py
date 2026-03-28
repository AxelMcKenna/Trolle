"""Add price_alerts and notifications tables

Revision ID: k0e1f2a3b4c5
Revises: j9d0e1f2a3b4
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "k0e1f2a3b4c5"
down_revision = "j9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "price_alerts",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_price", sa.Float, nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_index("ix_price_alerts_user", "price_alerts", ["user_id"])
    op.create_index("ix_price_alerts_active_product", "price_alerts", ["product_id", "is_active"])

    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alert_id", UUID(as_uuid=True), sa.ForeignKey("price_alerts.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.String(1024), nullable=False),
        sa.Column("is_read", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_index("ix_notifications_user_unread", "notifications", ["user_id", "is_read"])


def downgrade() -> None:
    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_price_alerts_active_product", table_name="price_alerts")
    op.drop_index("ix_price_alerts_user", table_name="price_alerts")
    op.drop_table("price_alerts")
