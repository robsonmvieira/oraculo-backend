"""add size_tag and activity_tag to community_stats

Revision ID: f7a8b9c0d1e2
Revises: fcbe8b1dfbfa
Create Date: 2026-02-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "community_stats",
        sa.Column("size_tag", sa.String(20), nullable=True),
    )
    op.add_column(
        "community_stats",
        sa.Column("activity_tag", sa.String(20), nullable=True),
    )

    # Backfill existing rows
    op.execute("""
        UPDATE community_stats SET size_tag = CASE
            WHEN subscribers > 1000000 THEN 'Massive'
            WHEN subscribers > 500000 THEN 'Huge'
            WHEN subscribers > 100000 THEN 'Large'
            WHEN subscribers > 50000 THEN 'Medium'
            WHEN subscribers IS NOT NULL THEN 'Small'
            ELSE NULL
        END
    """)
    op.execute("""
        UPDATE community_stats SET activity_tag = CASE
            WHEN growth_week > 0.3 THEN 'Super Active'
            WHEN growth_week > 0.15 THEN 'High Activity'
            WHEN growth_week > 0.05 THEN 'Active'
            WHEN growth_week > 0.01 THEN 'Moderate'
            WHEN growth_week IS NOT NULL THEN 'Low'
            ELSE NULL
        END
    """)


def downgrade() -> None:
    op.drop_column("community_stats", "activity_tag")
    op.drop_column("community_stats", "size_tag")
