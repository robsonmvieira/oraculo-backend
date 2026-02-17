"""add related_subs table

Revision ID: ccb9f70fdf09
Revises: fcbe8b1dfbfa
Create Date: 2026-02-17 20:30:21.966166

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ccb9f70fdf09'
down_revision: Union[str, Sequence[str], None] = 'fcbe8b1dfbfa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'related_subs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('source_sub', sa.String(100), nullable=False),
        sa.Column('related_sub', sa.String(100), nullable=False),
        sa.Column('related_sub_title', sa.String(500), nullable=True),
        sa.Column('related_sub_description', sa.Text(), nullable=True),
        sa.Column('related_sub_subscribers', sa.Integer(), nullable=True),
        sa.Column('discovered_via', sa.String(200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_related_subs_source_sub', 'related_subs', ['source_sub'])
    op.create_index('ix_related_subs_related_sub', 'related_subs', ['related_sub'])
    op.create_index('ix_related_subs_expires_at', 'related_subs', ['expires_at'])
    # Índice único para evitar duplicatas
    op.create_index(
        'ix_related_subs_unique',
        'related_subs',
        ['source_sub', 'related_sub'],
        unique=True
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_related_subs_unique', table_name='related_subs')
    op.drop_index('ix_related_subs_expires_at', table_name='related_subs')
    op.drop_index('ix_related_subs_related_sub', table_name='related_subs')
    op.drop_index('ix_related_subs_source_sub', table_name='related_subs')
    op.drop_table('related_subs')
