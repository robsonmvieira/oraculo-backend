"""add audience_topic_analyses and audience_topics tables

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-02-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

# revision identifiers, used by Alembic.
revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audience_topic_analyses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "audience_id",
            UUID(as_uuid=True),
            sa.ForeignKey("audiences.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, default="processing", index=True),
        sa.Column("communities_fingerprint", sa.String(64), nullable=False, index=True),
        sa.Column("total_topics", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "audience_topics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "analysis_id",
            UUID(as_uuid=True),
            sa.ForeignKey("audience_topic_analyses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("growth_percentage", sa.Float, nullable=True),
        sa.Column("mention_frequency", sa.Float, nullable=True),
        sa.Column("mention_period", sa.String(10), nullable=True),
        sa.Column("post_count", sa.Integer, nullable=True),
        sa.Column("communities", JSON, nullable=True),
        sa.Column("rank", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("audience_topics")
    op.drop_table("audience_topic_analyses")
