"""Add user_profiles and saved_trolleys tables

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-02-26

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # user_profiles — 1:1 with Supabase auth.users
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("preferred_radius_km", sa.Float(), nullable=False, server_default="2.0"),
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
    )

    # FK to auth.users (Supabase managed schema) — raw SQL because ORM can't reference cross-schema
    op.execute(
        "ALTER TABLE user_profiles "
        "ADD CONSTRAINT fk_user_profiles_auth_users "
        "FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE"
    )

    # saved_trolleys
    op.create_table(
        "saved_trolleys",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="'[]'::jsonb"),
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
    )
    op.create_index("ix_saved_trolleys_user", "saved_trolleys", ["user_id"])

    # RLS — defense-in-depth (API uses service role, but belt-and-suspenders)
    op.execute("ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE saved_trolleys ENABLE ROW LEVEL SECURITY")

    op.execute(
        "CREATE POLICY user_profiles_own ON user_profiles "
        "FOR ALL USING (id = auth.uid()) WITH CHECK (id = auth.uid())"
    )
    op.execute(
        "CREATE POLICY saved_trolleys_own ON saved_trolleys "
        "FOR ALL USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid())"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS saved_trolleys_own ON saved_trolleys")
    op.execute("DROP POLICY IF EXISTS user_profiles_own ON user_profiles")
    op.execute("ALTER TABLE saved_trolleys DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_profiles DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_saved_trolleys_user", table_name="saved_trolleys")
    op.drop_table("saved_trolleys")

    op.execute("ALTER TABLE user_profiles DROP CONSTRAINT IF EXISTS fk_user_profiles_auth_users")
    op.drop_table("user_profiles")
