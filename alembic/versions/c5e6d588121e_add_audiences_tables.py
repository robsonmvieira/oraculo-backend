"""add_audiences_tables

Revision ID: c5e6d588121e
Revises: 47f24572b171
Create Date: 2026-02-17 23:44:14.199130

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5e6d588121e'
down_revision: Union[str, Sequence[str], None] = '47f24572b171'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Tabela audiences
    op.create_table(
        'audiences',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audiences_name', 'audiences', ['name'])
    op.create_index('ix_audiences_user_id', 'audiences', ['user_id'])

    # Tabela audience_communities
    op.create_table(
        'audience_communities',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('audience_id', sa.UUID(), nullable=False),
        sa.Column('subreddit_name', sa.String(100), nullable=False),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['audience_id'], ['audiences.id'], ondelete='CASCADE')
    )
    op.create_index('ix_audience_communities_audience_id', 'audience_communities', ['audience_id'])
    op.create_index('ix_audience_communities_subreddit_name', 'audience_communities', ['subreddit_name'])
    op.create_unique_constraint(
        'uq_audience_community',
        'audience_communities',
        ['audience_id', 'subreddit_name']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_audience_community', 'audience_communities', type_='unique')
    op.drop_index('ix_audience_communities_subreddit_name', table_name='audience_communities')
    op.drop_index('ix_audience_communities_audience_id', table_name='audience_communities')
    op.drop_table('audience_communities')
    op.drop_index('ix_audiences_user_id', table_name='audiences')
    op.drop_index('ix_audiences_name', table_name='audiences')
    op.drop_table('audiences')
