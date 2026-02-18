"""add_audience_templates_tables

Revision ID: 2474fe850689
Revises: c5e6d588121e
Create Date: 2026-02-18 21:14:44.144332

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2474fe850689'
down_revision: Union[str, Sequence[str], None] = 'c5e6d588121e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Tabela de templates de audiência (audiências pré-definidas)
    op.create_table(
        'audience_templates',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('slug', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icon', sa.String(100), nullable=True),  # emoji ou icon name
        sa.Column('category', sa.String(100), nullable=True),  # "business", "lifestyle", "tech"
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('display_order', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_audience_templates_slug', 'audience_templates', ['slug'], unique=True)
    op.create_index('ix_audience_templates_category', 'audience_templates', ['category'])
    op.create_index('ix_audience_templates_is_active', 'audience_templates', ['is_active'])

    # Tabela de comunidades dentro de cada template
    op.create_table(
        'audience_template_communities',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('template_id', sa.UUID(), nullable=False),
        sa.Column('subreddit_name', sa.String(100), nullable=False),
        sa.Column('added_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['template_id'], ['audience_templates.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_audience_template_communities_template_id', 'audience_template_communities', ['template_id'])
    op.create_index(
        'ix_audience_template_communities_unique',
        'audience_template_communities',
        ['template_id', 'subreddit_name'],
        unique=True
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_audience_template_communities_unique', 'audience_template_communities')
    op.drop_index('ix_audience_template_communities_template_id', 'audience_template_communities')
    op.drop_table('audience_template_communities')
    op.drop_index('ix_audience_templates_is_active', 'audience_templates')
    op.drop_index('ix_audience_templates_category', 'audience_templates')
    op.drop_index('ix_audience_templates_slug', 'audience_templates')
    op.drop_table('audience_templates')
