"""add_intent_classification_tables

Revision ID: dbdaec64de50
Revises: fe587c53c177
Create Date: 2026-02-25 14:02:20.399219

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'dbdaec64de50'
down_revision: Union[str, Sequence[str], None] = 'fe587c53c177'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('intent_classification_analyses',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('theme_analysis_id', sa.UUID(), nullable=False),
    sa.Column('audience_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('time_window', sa.String(length=10), nullable=False),
    sa.Column('fingerprint', sa.String(length=64), nullable=False),
    sa.Column('total_posts_classified', sa.Integer(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['audience_id'], ['audiences.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['theme_analysis_id'], ['theme_analyses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_intent_classification_analyses_audience_id'), 'intent_classification_analyses', ['audience_id'], unique=False)
    op.create_index(op.f('ix_intent_classification_analyses_fingerprint'), 'intent_classification_analyses', ['fingerprint'], unique=False)
    op.create_index(op.f('ix_intent_classification_analyses_status'), 'intent_classification_analyses', ['status'], unique=False)
    op.create_index(op.f('ix_intent_classification_analyses_theme_analysis_id'), 'intent_classification_analyses', ['theme_analysis_id'], unique=False)
    op.create_table('intent_summaries',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('analysis_id', sa.UUID(), nullable=False),
    sa.Column('intent_category', sa.String(length=30), nullable=False),
    sa.Column('post_count', sa.Integer(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('top_subreddits', sa.JSON(), nullable=True),
    sa.Column('sample_posts', sa.JSON(), nullable=True),
    sa.Column('rank', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['analysis_id'], ['intent_classification_analyses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_intent_summaries_analysis_id'), 'intent_summaries', ['analysis_id'], unique=False)
    op.create_table('post_intent_classifications',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('analysis_id', sa.UUID(), nullable=False),
    sa.Column('post_reddit_id', sa.String(length=20), nullable=False),
    sa.Column('post_title', sa.String(length=500), nullable=False),
    sa.Column('post_subreddit', sa.String(length=100), nullable=False),
    sa.Column('primary_intent', sa.String(length=30), nullable=False),
    sa.Column('secondary_intent', sa.String(length=30), nullable=True),
    sa.Column('confidence', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['analysis_id'], ['intent_classification_analyses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_post_intent_classifications_analysis_id'), 'post_intent_classifications', ['analysis_id'], unique=False)
    op.create_index(op.f('ix_post_intent_classifications_primary_intent'), 'post_intent_classifications', ['primary_intent'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_post_intent_classifications_primary_intent'), table_name='post_intent_classifications')
    op.drop_index(op.f('ix_post_intent_classifications_analysis_id'), table_name='post_intent_classifications')
    op.drop_table('post_intent_classifications')
    op.drop_index(op.f('ix_intent_summaries_analysis_id'), table_name='intent_summaries')
    op.drop_table('intent_summaries')
    op.drop_index(op.f('ix_intent_classification_analyses_theme_analysis_id'), table_name='intent_classification_analyses')
    op.drop_index(op.f('ix_intent_classification_analyses_status'), table_name='intent_classification_analyses')
    op.drop_index(op.f('ix_intent_classification_analyses_fingerprint'), table_name='intent_classification_analyses')
    op.drop_index(op.f('ix_intent_classification_analyses_audience_id'), table_name='intent_classification_analyses')
    op.drop_table('intent_classification_analyses')
