"""add_content_suggestion_tables

Revision ID: cdf0ccae0876
Revises: a3b2c1d0e5f4
Create Date: 2026-03-01 21:23:17.326207

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'cdf0ccae0876'
down_revision: Union[str, Sequence[str], None] = 'a3b2c1d0e5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'content_suggestion_analyses',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('audience_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('fingerprint', sa.String(length=64), nullable=False),
        sa.Column('modules_used', sa.JSON(), nullable=True),
        sa.Column('model_used', sa.String(length=100), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['audience_id'], ['audiences.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('audience_id', 'fingerprint', name='uq_cs_audience_fingerprint'),
    )
    op.create_index(op.f('ix_content_suggestion_analyses_audience_id'), 'content_suggestion_analyses', ['audience_id'])
    op.create_index(op.f('ix_content_suggestion_analyses_user_id'), 'content_suggestion_analyses', ['user_id'])
    op.create_index(op.f('ix_content_suggestion_analyses_fingerprint'), 'content_suggestion_analyses', ['fingerprint'])

    op.create_table(
        'content_suggestions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('analysis_id', sa.UUID(), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('priority', sa.String(length=10), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('approach', sa.Text(), nullable=False),
        sa.Column('why_now', sa.Text(), nullable=False),
        sa.Column('evidence', sa.JSON(), nullable=True),
        sa.Column('format', sa.String(length=30), nullable=False),
        sa.Column('format_rationale', sa.Text(), nullable=True),
        sa.Column('emotional_tone', sa.String(length=30), nullable=False),
        sa.Column('tone_rationale', sa.Text(), nullable=True),
        sa.Column('outline', sa.JSON(), nullable=True),
        sa.Column('keywords', sa.JSON(), nullable=True),
        sa.Column('research_notes', sa.Text(), nullable=True),
        sa.Column('image_prompt', sa.Text(), nullable=True),
        sa.Column('differentiation_notes', sa.Text(), nullable=True),
        sa.Column('accuracy_notes', sa.Text(), nullable=True),
        sa.Column('source_topics', sa.JSON(), nullable=True),
        sa.Column('source_modules', sa.JSON(), nullable=True),
        sa.Column('feedback_status', sa.String(length=20), nullable=True),
        sa.Column('feedback_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['analysis_id'], ['content_suggestion_analyses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_content_suggestions_analysis_id'), 'content_suggestions', ['analysis_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_content_suggestions_analysis_id'), table_name='content_suggestions')
    op.drop_table('content_suggestions')
    op.drop_index(op.f('ix_content_suggestion_analyses_fingerprint'), table_name='content_suggestion_analyses')
    op.drop_index(op.f('ix_content_suggestion_analyses_user_id'), table_name='content_suggestion_analyses')
    op.drop_index(op.f('ix_content_suggestion_analyses_audience_id'), table_name='content_suggestion_analyses')
    op.drop_table('content_suggestion_analyses')
