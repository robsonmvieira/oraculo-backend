"""add topic_deep_dive_analyses and topic_deep_dives tables

Revision ID: d0e1f2a3b4c5
Revises: c0d1e2f3a4b5
Create Date: 2026-02-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

# revision identifiers, used by Alembic.
revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "topic_deep_dive_analyses",
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
        sa.Column("status", sa.String(20), nullable=False, default="processing", index=True),
        sa.Column("topic_fingerprint", sa.String(64), nullable=False, index=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "topic_deep_dives",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "analysis_id",
            UUID(as_uuid=True),
            sa.ForeignKey("topic_deep_dive_analyses.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("subtopics", JSON, nullable=True),
        sa.Column("common_questions", JSON, nullable=True),
        sa.Column("sentiment", JSON, nullable=True),
        sa.Column("mentioned_products", JSON, nullable=True),
        sa.Column("representative_posts", JSON, nullable=True),
        sa.Column("actionable_insights", JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("topic_deep_dives")
    op.drop_table("topic_deep_dive_analyses")
