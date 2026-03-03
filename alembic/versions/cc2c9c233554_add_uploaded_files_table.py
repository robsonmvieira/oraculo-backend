"""add uploaded_files table

Revision ID: cc2c9c233554
Revises: c1d2e3f4a5b6
Create Date: 2026-03-03 09:55:08.415138

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'cc2c9c233554'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('uploaded_files',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('key', sa.String(length=500), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('content_type', sa.String(length=100), nullable=False),
    sa.Column('size_bytes', sa.BigInteger(), nullable=True),
    sa.Column('original_name', sa.String(length=500), nullable=True),
    sa.Column('uploaded_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_uploaded_files_key'), 'uploaded_files', ['key'], unique=True)
    op.create_index(op.f('ix_uploaded_files_uploaded_by'), 'uploaded_files', ['uploaded_by'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_uploaded_files_uploaded_by'), table_name='uploaded_files')
    op.drop_index(op.f('ix_uploaded_files_key'), table_name='uploaded_files')
    op.drop_table('uploaded_files')
