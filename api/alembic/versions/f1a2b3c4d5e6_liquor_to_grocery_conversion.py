"""Liquor to grocery conversion

Drop liquor-specific columns, add grocery columns, truncate stale data.

Revision ID: f1a2b3c4d5e6
Revises: b7c8d9e0f1a2
Create Date: 2026-02-22 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Truncate stale data from old liquor domain
    op.execute("TRUNCATE TABLE prices CASCADE")
    op.execute("TRUNCATE TABLE products CASCADE")
    op.execute("TRUNCATE TABLE ingestion_runs CASCADE")

    # Delete stores for liquor-only chains
    op.execute(
        "DELETE FROM stores WHERE chain NOT IN ('countdown', 'new_world', 'paknsave')"
    )

    # Drop liquor columns from products
    op.drop_column("products", "abv_percent")
    op.drop_column("products", "pack_count")
    op.drop_column("products", "unit_volume_ml")
    op.drop_column("products", "total_volume_ml")

    # Add grocery columns to products
    op.add_column("products", sa.Column("size", sa.String(64), nullable=True))
    op.add_column("products", sa.Column("department", sa.String(64), nullable=True))
    op.add_column("products", sa.Column("subcategory", sa.String(128), nullable=True))
    op.add_column("products", sa.Column("unit_price", sa.Float(), nullable=True))
    op.add_column("products", sa.Column("unit_measure", sa.String(16), nullable=True))

    # Add indexes for department and subcategory
    op.create_index("ix_product_department", "products", ["department"])
    op.create_index("ix_product_subcategory", "products", ["subcategory"])


def downgrade() -> None:
    # Drop grocery indexes
    op.drop_index("ix_product_subcategory", table_name="products")
    op.drop_index("ix_product_department", table_name="products")

    # Drop grocery columns
    op.drop_column("products", "unit_measure")
    op.drop_column("products", "unit_price")
    op.drop_column("products", "subcategory")
    op.drop_column("products", "department")
    op.drop_column("products", "size")

    # Restore liquor columns
    op.add_column("products", sa.Column("total_volume_ml", sa.Float(), nullable=True))
    op.add_column("products", sa.Column("unit_volume_ml", sa.Float(), nullable=True))
    op.add_column("products", sa.Column("pack_count", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("abv_percent", sa.Float(), nullable=True))
