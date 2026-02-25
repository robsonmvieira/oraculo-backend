"""add_theme_posts_table

Revision ID: fe587c53c177
Revises: 71731c50ceea
Create Date: 2026-02-25 13:52:05.545719

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'fe587c53c177'
down_revision: Union[str, Sequence[str], None] = '71731c50ceea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('theme_posts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('analysis_id', sa.UUID(), nullable=False),
    sa.Column('post_reddit_id', sa.String(length=20), nullable=False),
    sa.Column('subreddit', sa.String(length=100), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('selftext', sa.Text(), nullable=True),
    sa.Column('score', sa.Integer(), nullable=True),
    sa.Column('num_comments', sa.Integer(), nullable=True),
    sa.Column('created_utc', sa.Float(), nullable=True),
    sa.Column('permalink', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['analysis_id'], ['theme_analyses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_theme_posts_analysis_id'), 'theme_posts', ['analysis_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_theme_posts_analysis_id'), table_name='theme_posts')
    op.drop_table('theme_posts')
