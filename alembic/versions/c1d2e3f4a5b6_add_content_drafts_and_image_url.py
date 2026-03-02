"""add_content_drafts_and_image_url

Revision ID: c1d2e3f4a5b6
Revises: b4e7f2a1c893
Create Date: 2026-03-02 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'b4e7f2a1c893'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Adicionar image_url na tabela content_suggestions
    op.add_column(
        'content_suggestions',
        sa.Column('image_url', sa.Text(), nullable=True),
    )

    # Criar tabela content_drafts
    op.create_table(
        'content_drafts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'suggestion_id',
            UUID(as_uuid=True),
            sa.ForeignKey('content_suggestions.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column('platform', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='processing'),
        sa.Column('hooks', sa.JSON(), nullable=True),
        sa.Column('full_draft', sa.Text(), nullable=True),
        sa.Column('narrative_arc', sa.Text(), nullable=True),
        sa.Column('cta', sa.Text(), nullable=True),
        sa.Column('platform_notes', sa.Text(), nullable=True),
        sa.Column('hashtags', sa.JSON(), nullable=True),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('image_aspect_ratio', sa.String(10), nullable=True),
        sa.Column('model_used', sa.String(100), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('content_drafts')
    op.drop_column('content_suggestions', 'image_url')
