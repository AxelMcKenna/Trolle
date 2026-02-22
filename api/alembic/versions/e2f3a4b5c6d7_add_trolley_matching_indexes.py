"""Add composite trigram index for trolley cross-chain matching

Revision ID: e2f3a4b5c6d7
Revises: c4d5e6f7a8b9
Create Date: 2026-02-23

Adds a composite GIN trgm index on lower(name || ' ' || coalesce(size, ''))
for fuzzy similarity queries used by trolley cross-chain matching.
pg_trgm extension already enabled by migration b7c8d9e0f1a2.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_products_name_size_trgm
        ON products USING gin (lower(name || ' ' || coalesce(size, '')) gin_trgm_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_products_name_size_trgm")
