"""add llm_cache table

Revision ID: fcbe8b1dfbfa
Revises:
Create Date: 2026-02-17 18:15:25.628135

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fcbe8b1dfbfa'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'llm_cache',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('input_hash', sa.String(64), nullable=False),
        sa.Column('task_type', sa.String(50), nullable=False),
        sa.Column('input_text', sa.Text(), nullable=False),
        sa.Column('result_json', sa.JSON(), nullable=False),
        sa.Column('ttl_hours', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_llm_cache_input_hash', 'llm_cache', ['input_hash'])
    op.create_index('ix_llm_cache_task_type', 'llm_cache', ['task_type'])
    op.create_index('ix_llm_cache_expires_at', 'llm_cache', ['expires_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_llm_cache_expires_at', table_name='llm_cache')
    op.drop_index('ix_llm_cache_task_type', table_name='llm_cache')
    op.drop_index('ix_llm_cache_input_hash', table_name='llm_cache')
    op.drop_table('llm_cache')
