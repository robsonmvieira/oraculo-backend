"""add youtube validation tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f7
Create Date: 2026-03-04 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "youtube_validations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("audience_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="processing",
        ),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("analysis_data", sa.JSON(), nullable=True),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("total_videos", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("total_comments", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("model_used", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["audience_id"], ["audiences.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_youtube_validations_audience_id"),
        "youtube_validations",
        ["audience_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_youtube_validations_user_id"),
        "youtube_validations",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_youtube_validations_status"),
        "youtube_validations",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_youtube_validations_fingerprint"),
        "youtube_validations",
        ["fingerprint"],
        unique=False,
    )

    op.create_table(
        "youtube_collected_videos",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("validation_id", sa.UUID(), nullable=False),
        sa.Column("topic_name", sa.String(length=255), nullable=False),
        sa.Column("video_id", sa.String(length=20), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("channel_name", sa.Text(), nullable=True),
        sa.Column("views", sa.Integer(), nullable=True),
        sa.Column("likes", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("comments", sa.JSON(), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("transcript_lang", sa.String(length=10), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["validation_id"],
            ["youtube_validations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_youtube_collected_videos_validation_id"),
        "youtube_collected_videos",
        ["validation_id"],
        unique=False,
    )
    op.create_index(
        "ix_yt_collected_validation_topic",
        "youtube_collected_videos",
        ["validation_id", "topic_name"],
        unique=False,
    )
    op.create_index(
        "ix_yt_collected_unique",
        "youtube_collected_videos",
        ["validation_id", "video_id"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_yt_collected_unique",
        table_name="youtube_collected_videos",
    )
    op.drop_index(
        "ix_yt_collected_validation_topic",
        table_name="youtube_collected_videos",
    )
    op.drop_index(
        op.f("ix_youtube_collected_videos_validation_id"),
        table_name="youtube_collected_videos",
    )
    op.drop_table("youtube_collected_videos")
    op.drop_index(
        op.f("ix_youtube_validations_fingerprint"),
        table_name="youtube_validations",
    )
    op.drop_index(
        op.f("ix_youtube_validations_status"),
        table_name="youtube_validations",
    )
    op.drop_index(
        op.f("ix_youtube_validations_user_id"),
        table_name="youtube_validations",
    )
    op.drop_index(
        op.f("ix_youtube_validations_audience_id"),
        table_name="youtube_validations",
    )
    op.drop_table("youtube_validations")
