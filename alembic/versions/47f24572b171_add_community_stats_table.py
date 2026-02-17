"""add_community_stats_table

Revision ID: 47f24572b171
Revises: ccb9f70fdf09
Create Date: 2026-02-17 23:36:45.576112

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '47f24572b171'
down_revision: Union[str, Sequence[str], None] = 'ccb9f70fdf09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'community_stats',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('subreddit_name', sa.String(100), nullable=False),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('subscribers', sa.Integer(), nullable=True),
        sa.Column('icon_url', sa.String(1000), nullable=True),
        sa.Column('growth_week', sa.Float(), nullable=True),
        sa.Column('growth_month', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_community_stats_subreddit_name', 'community_stats', ['subreddit_name'], unique=True)
    op.create_index('ix_community_stats_growth_week', 'community_stats', ['growth_week'])
    op.create_index('ix_community_stats_updated_at', 'community_stats', ['updated_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_community_stats_updated_at', table_name='community_stats')
    op.drop_index('ix_community_stats_growth_week', table_name='community_stats')
    op.drop_index('ix_community_stats_subreddit_name', table_name='community_stats')
    op.drop_table('community_stats')
