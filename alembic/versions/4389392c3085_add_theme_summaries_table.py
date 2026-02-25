"""add theme_summaries table

Revision ID: 4389392c3085
Revises: dbdaec64de50
Create Date: 2026-02-25 17:01:42.102706

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4389392c3085'
down_revision: Union[str, Sequence[str], None] = 'dbdaec64de50'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('theme_summaries',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('theme_id', sa.UUID(), nullable=False),
    sa.Column('analysis_id', sa.UUID(), nullable=False),
    sa.Column('narrative', sa.Text(), nullable=True),
    sa.Column('highlights', sa.JSON(), nullable=True),
    sa.Column('emotional_tone', sa.String(length=30), nullable=True),
    sa.Column('tone_description', sa.String(length=200), nullable=True),
    sa.Column('key_themes', sa.JSON(), nullable=True),
    sa.Column('intent_breakdown', sa.JSON(), nullable=True),
    sa.Column('week_differentiator', sa.Text(), nullable=True),
    sa.Column('fingerprint', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['analysis_id'], ['theme_analyses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['theme_id'], ['themes.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_theme_summaries_analysis_id'), 'theme_summaries', ['analysis_id'], unique=False)
    op.create_index(op.f('ix_theme_summaries_fingerprint'), 'theme_summaries', ['fingerprint'], unique=False)
    op.create_index(op.f('ix_theme_summaries_theme_id'), 'theme_summaries', ['theme_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_theme_summaries_theme_id'), table_name='theme_summaries')
    op.drop_index(op.f('ix_theme_summaries_fingerprint'), table_name='theme_summaries')
    op.drop_index(op.f('ix_theme_summaries_analysis_id'), table_name='theme_summaries')
    op.drop_table('theme_summaries')
