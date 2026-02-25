"""add theme_panels table

Revision ID: 8bdebac3c5cf
Revises: 4389392c3085
Create Date: 2026-02-25 21:11:12.958884

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8bdebac3c5cf'
down_revision: Union[str, Sequence[str], None] = '4389392c3085'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('theme_panels',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('theme_id', sa.UUID(), nullable=False),
    sa.Column('analysis_id', sa.UUID(), nullable=False),
    sa.Column('subcategories', sa.JSON(), nullable=True),
    sa.Column('related_topics', sa.JSON(), nullable=True),
    sa.Column('subreddit_distribution', sa.JSON(), nullable=True),
    sa.Column('action_links', sa.JSON(), nullable=True),
    sa.Column('fingerprint', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['analysis_id'], ['theme_analyses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['theme_id'], ['themes.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_theme_panels_analysis_id'), 'theme_panels', ['analysis_id'], unique=False)
    op.create_index(op.f('ix_theme_panels_fingerprint'), 'theme_panels', ['fingerprint'], unique=False)
    op.create_index(op.f('ix_theme_panels_theme_id'), 'theme_panels', ['theme_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_theme_panels_theme_id'), table_name='theme_panels')
    op.drop_index(op.f('ix_theme_panels_fingerprint'), table_name='theme_panels')
    op.drop_index(op.f('ix_theme_panels_analysis_id'), table_name='theme_panels')
    op.drop_table('theme_panels')
