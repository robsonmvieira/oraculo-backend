"""add_pgvector_and_embeddings

Revision ID: a1b2c3d4e5f6
Revises: 2474fe850689
Create Date: 2026-02-19

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "2474fe850689"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Table for community embeddings
    op.create_table(
        "community_embeddings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("subreddit_name", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("subscribers", sa.Integer(), nullable=True),
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
    op.create_index(
        "idx_community_embeddings_name",
        "community_embeddings",
        ["subreddit_name"],
        unique=True,
    )

    # Table for user feedback on community suggestions
    op.create_table(
        "user_community_feedback",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(100), nullable=True),
        sa.Column("subreddit_name", sa.String(100), nullable=False),
        sa.Column("context_type", sa.String(50), nullable=False),
        sa.Column("context_id", sa.UUID(), nullable=True),
        sa.Column("feedback", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_feedback_user",
        "user_community_feedback",
        ["user_id"],
    )
    op.create_index(
        "idx_feedback_subreddit",
        "user_community_feedback",
        ["subreddit_name"],
    )
    op.create_unique_constraint(
        "uq_user_community_feedback",
        "user_community_feedback",
        ["user_id", "subreddit_name", "context_type", "context_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("user_community_feedback")
    op.drop_table("community_embeddings")
    op.execute("DROP EXTENSION IF EXISTS vector")
