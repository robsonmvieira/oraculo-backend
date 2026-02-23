"""add topic_sentiment tables, drop sentiment from deep_dives, drop emerging_opinions from patterns

Revision ID: b4c5d6e7f8a9
Revises: a3bb06f1821e
Create Date: 2026-02-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

# revision identifiers, used by Alembic.
revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, None] = "a3bb06f1821e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create topic_sentiment_analyses table
    op.create_table(
        "topic_sentiment_analyses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "topic_id",
            UUID(as_uuid=True),
            sa.ForeignKey("audience_topics.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "audience_id",
            UUID(as_uuid=True),
            sa.ForeignKey("audiences.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="processing",
            index=True,
        ),
        sa.Column("topic_fingerprint", sa.String(64), nullable=False, index=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 2. Create topic_sentiments table
    op.create_table(
        "topic_sentiments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "analysis_id",
            UUID(as_uuid=True),
            sa.ForeignKey("topic_sentiment_analyses.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("overall_sentiment", JSON, nullable=True),
        sa.Column("emotional_map", JSON, nullable=True),
        sa.Column("sentiment_by_community", JSON, nullable=True),
        sa.Column("sentiment_by_subtopic", JSON, nullable=True),
        sa.Column("sentiment_drivers", JSON, nullable=True),
        sa.Column("tension_points", JSON, nullable=True),
        sa.Column("pain_points", JSON, nullable=True),
        sa.Column("sentiment_opportunities", JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 3. Drop sentiment column from topic_deep_dives
    op.drop_column("topic_deep_dives", "sentiment")

    # 4. Drop emerging_opinions column from topic_patterns
    op.drop_column("topic_patterns", "emerging_opinions")


def downgrade() -> None:
    # Reverse order
    op.add_column(
        "topic_patterns",
        sa.Column("emerging_opinions", JSON, nullable=True),
    )
    op.add_column(
        "topic_deep_dives",
        sa.Column("sentiment", JSON, nullable=True),
    )
    op.drop_table("topic_sentiments")
    op.drop_table("topic_sentiment_analyses")
