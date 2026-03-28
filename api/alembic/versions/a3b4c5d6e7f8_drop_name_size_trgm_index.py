"""Drop obsolete name+size composite trigram index

Revision ID: a3b4c5d6e7f8
Revises: 79a4acac15c8
Create Date: 2026-02-26

Cross-chain matching no longer concatenates name+size for similarity.
Similarity is now computed on cleaned name only, so the composite index
is unused. The existing ix_products_name_trgm on lower(name) handles
candidate filtering.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "79a4acac15c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_products_name_size_trgm")


def downgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_products_name_size_trgm
        ON products USING gin (lower(name || ' ' || coalesce(size, '')) gin_trgm_ops)
        """
    )
