"""add audience_keyword_analyses and audience_keywords tables

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-02-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "b9c0d1e2f3a4"
down_revision: Union[str, None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audience_keyword_analyses",
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
        sa.Column("total_keywords", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "audience_keywords",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "analysis_id",
            UUID(as_uuid=True),
            sa.ForeignKey("audience_keyword_analyses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("keyword", sa.String(200), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("relevance_score", sa.Integer, nullable=True),
        sa.Column("rank", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("audience_keywords")
    op.drop_table("audience_keyword_analyses")
