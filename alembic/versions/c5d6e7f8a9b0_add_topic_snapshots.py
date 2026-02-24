"""add topic_snapshots table

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-02-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

# revision identifiers, used by Alembic.
revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "topic_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "audience_id",
            UUID(as_uuid=True),
            sa.ForeignKey("audiences.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "analysis_id",
            UUID(as_uuid=True),
            sa.ForeignKey("audience_topic_analyses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("topic_name", sa.String(200), nullable=False),
        sa.Column("topic_name_normalized", sa.String(200), nullable=False, index=True),
        sa.Column("mention_frequency", sa.Float, nullable=True),
        sa.Column("mention_period", sa.String(10), nullable=True),
        sa.Column("post_count", sa.Integer, nullable=True),
        sa.Column("growth_percentage", sa.Float, nullable=True),
        sa.Column("communities", JSON, nullable=True),
        sa.Column("snapshot_date", sa.Date, nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_topic_snapshots_audience_name_date",
        "topic_snapshots",
        ["audience_id", "topic_name_normalized", "snapshot_date"],
    )
    op.create_index(
        "ix_topic_snapshots_audience_date",
        "topic_snapshots",
        ["audience_id", "snapshot_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_topic_snapshots_audience_date", table_name="topic_snapshots")
    op.drop_index("ix_topic_snapshots_audience_name_date", table_name="topic_snapshots")
    op.drop_table("topic_snapshots")
