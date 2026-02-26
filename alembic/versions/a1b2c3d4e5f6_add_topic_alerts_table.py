"""add topic_alerts table

Revision ID: a1b2c3d4e5f6
Revises: 8bdebac3c5cf
Create Date: 2026-02-26 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "8bdebac3c5cf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "topic_alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "audience_id",
            UUID(as_uuid=True),
            sa.ForeignKey("audiences.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alert_type", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False, server_default="info"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("metadata", JSON, nullable=False, server_default="{}"),
        sa.Column("is_dismissed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )

    op.create_index("ix_topic_alerts_audience_id", "topic_alerts", ["audience_id"])
    op.create_index("ix_topic_alerts_user_id", "topic_alerts", ["user_id"])
    op.create_index(
        "ix_topic_alerts_audience_type", "topic_alerts", ["audience_id", "alert_type"]
    )
    op.create_index(
        "ix_topic_alerts_user_not_dismissed",
        "topic_alerts",
        ["user_id", "is_dismissed"],
        postgresql_where=sa.text("is_dismissed = false"),
    )


def downgrade() -> None:
    op.drop_index("ix_topic_alerts_user_not_dismissed", table_name="topic_alerts")
    op.drop_index("ix_topic_alerts_audience_type", table_name="topic_alerts")
    op.drop_index("ix_topic_alerts_user_id", table_name="topic_alerts")
    op.drop_index("ix_topic_alerts_audience_id", table_name="topic_alerts")
    op.drop_table("topic_alerts")
