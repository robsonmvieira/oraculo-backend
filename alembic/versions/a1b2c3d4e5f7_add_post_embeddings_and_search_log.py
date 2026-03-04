"""add_post_embeddings_and_search_log

Revision ID: a1b2c3d4e5f7
Revises: d7a1b2c3e4f5
Create Date: 2026-03-04 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, Sequence[str], None] = "d7a1b2c3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "post_embeddings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("post_reddit_id", sa.String(length=20), nullable=False),
        sa.Column("subreddit", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("selftext_hash", sa.String(length=64), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_post_embeddings_post_reddit_id"),
        "post_embeddings",
        ["post_reddit_id"],
        unique=True,
    )

    op.create_table(
        "semantic_search_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("audience_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("total_posts_searched", sa.Integer(), nullable=True),
        sa.Column("total_posts_matched", sa.Integer(), nullable=True),
        sa.Column("pattern_count", sa.Integer(), nullable=True),
        sa.Column(
            "context_quality",
            sa.String(length=20),
            nullable=False,
            server_default="limited",
        ),
        sa.Column(
            "cached", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["audience_id"], ["audiences.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_semantic_search_logs_audience_id"),
        "semantic_search_logs",
        ["audience_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_semantic_search_logs_user_id"),
        "semantic_search_logs",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_semantic_search_logs_user_id"),
        table_name="semantic_search_logs",
    )
    op.drop_index(
        op.f("ix_semantic_search_logs_audience_id"),
        table_name="semantic_search_logs",
    )
    op.drop_table("semantic_search_logs")
    op.drop_index(
        op.f("ix_post_embeddings_post_reddit_id"),
        table_name="post_embeddings",
    )
    op.drop_table("post_embeddings")
