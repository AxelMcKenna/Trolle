"""Add barcode column to products table

Revision ID: n3b4c5d6e7f8
Revises: m2a3b4c5d6e7
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "n3b4c5d6e7f8"
down_revision = "m2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("barcode", sa.String(64), nullable=True))
    op.create_index("ix_product_barcode", "products", ["barcode"])


def downgrade() -> None:
    op.drop_index("ix_product_barcode", table_name="products")
    op.drop_column("products", "barcode")
