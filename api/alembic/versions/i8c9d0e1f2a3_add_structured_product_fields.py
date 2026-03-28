"""Add structured normalization fields to products

Revision ID: i8c9d0e1f2a3
Revises: h7b8c9d0e1f2
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "i8c9d0e1f2a3"
down_revision = "h7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("volume_ml", sa.Float(), nullable=True))
    op.add_column("products", sa.Column("weight_g", sa.Float(), nullable=True))
    op.add_column("products", sa.Column("pack_count", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("normalized_name", sa.String(255), nullable=True))
    op.add_column("products", sa.Column("normalized_brand", sa.String(128), nullable=True))

    op.create_index("ix_product_volume_ml", "products", ["volume_ml"])
    op.create_index("ix_product_weight_g", "products", ["weight_g"])
    op.create_index("ix_product_dept_volume", "products", ["department", "volume_ml"])
    op.create_index("ix_product_dept_weight", "products", ["department", "weight_g"])


def downgrade() -> None:
    op.drop_index("ix_product_dept_weight", table_name="products")
    op.drop_index("ix_product_dept_volume", table_name="products")
    op.drop_index("ix_product_weight_g", table_name="products")
    op.drop_index("ix_product_volume_ml", table_name="products")

    op.drop_column("products", "normalized_brand")
    op.drop_column("products", "normalized_name")
    op.drop_column("products", "pack_count")
    op.drop_column("products", "weight_g")
    op.drop_column("products", "volume_ml")
