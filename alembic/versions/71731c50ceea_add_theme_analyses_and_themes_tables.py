"""add theme_analyses and themes tables

Revision ID: 71731c50ceea
Revises: e7f8a9b0c1d2
Create Date: 2026-02-25 11:54:12.717133

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '71731c50ceea'
down_revision: Union[str, Sequence[str], None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('theme_analyses',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('audience_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('time_window', sa.String(length=10), nullable=False),
    sa.Column('period_start', sa.Date(), nullable=True),
    sa.Column('period_end', sa.Date(), nullable=True),
    sa.Column('communities_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('total_themes', sa.Integer(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['audience_id'], ['audiences.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_theme_analyses_audience_id'), 'theme_analyses', ['audience_id'], unique=False)
    op.create_index(op.f('ix_theme_analyses_communities_fingerprint'), 'theme_analyses', ['communities_fingerprint'], unique=False)
    op.create_index(op.f('ix_theme_analyses_status'), 'theme_analyses', ['status'], unique=False)
    op.create_index(op.f('ix_theme_analyses_time_window'), 'theme_analyses', ['time_window'], unique=False)
    op.create_table('themes',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('analysis_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('post_count', sa.Integer(), nullable=True),
    sa.Column('avg_score', sa.Float(), nullable=True),
    sa.Column('avg_comments', sa.Float(), nullable=True),
    sa.Column('engagement_score', sa.Float(), nullable=True),
    sa.Column('top_subreddits', sa.JSON(), nullable=True),
    sa.Column('top_keywords', sa.JSON(), nullable=True),
    sa.Column('representative_posts', sa.JSON(), nullable=True),
    sa.Column('rank', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['analysis_id'], ['theme_analyses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_themes_analysis_id'), 'themes', ['analysis_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_themes_analysis_id'), table_name='themes')
    op.drop_table('themes')
    op.drop_index(op.f('ix_theme_analyses_time_window'), table_name='theme_analyses')
    op.drop_index(op.f('ix_theme_analyses_status'), table_name='theme_analyses')
    op.drop_index(op.f('ix_theme_analyses_communities_fingerprint'), table_name='theme_analyses')
    op.drop_index(op.f('ix_theme_analyses_audience_id'), table_name='theme_analyses')
    op.drop_table('theme_analyses')
