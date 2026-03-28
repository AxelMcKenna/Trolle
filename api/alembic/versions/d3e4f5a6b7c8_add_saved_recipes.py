"""Add saved_recipes table

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-02-26

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_recipes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("recipe_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "recipe_id", name="uq_saved_recipe_user_recipe"),
    )
    op.create_index("ix_saved_recipes_user", "saved_recipes", ["user_id"])

    # RLS
    op.execute("ALTER TABLE saved_recipes ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY saved_recipes_own ON saved_recipes "
        "FOR ALL USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid())"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS saved_recipes_own ON saved_recipes")
    op.execute("ALTER TABLE saved_recipes DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_saved_recipes_user", table_name="saved_recipes")
    op.drop_table("saved_recipes")
