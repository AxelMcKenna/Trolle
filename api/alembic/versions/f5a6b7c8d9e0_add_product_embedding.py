"""add product embedding column with pgvector

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f5a6b7c8d9e0"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("products", sa.Column("embedding", sa.Text(), nullable=True))
    # Change column type to vector(384) — Alembic doesn't have a native vector type
    op.execute("ALTER TABLE products ALTER COLUMN embedding TYPE vector(384) USING embedding::vector(384)")
    op.execute(
        "CREATE INDEX ix_products_embedding_hnsw ON products "
        "USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_products_embedding_hnsw")
    op.drop_column("products", "embedding")
