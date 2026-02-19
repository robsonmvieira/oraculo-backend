"""add_category_to_community_stats

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-19

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add category column to community_stats."""
    op.add_column(
        "community_stats", sa.Column("category", sa.String(50), nullable=True)
    )
    op.create_index(
        "ix_community_stats_category", "community_stats", ["category"]
    )


def downgrade() -> None:
    """Remove category column from community_stats."""
    op.drop_index("ix_community_stats_category", table_name="community_stats")
    op.drop_column("community_stats", "category")
