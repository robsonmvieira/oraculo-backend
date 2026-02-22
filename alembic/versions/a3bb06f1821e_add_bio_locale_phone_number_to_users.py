"""add bio locale phone_number to users

Revision ID: a3bb06f1821e
Revises: a0b1c2d3e4f5
Create Date: 2026-02-22 23:25:28.932363

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3bb06f1821e'
down_revision: Union[str, Sequence[str], None] = 'a0b1c2d3e4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('bio', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('locale', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('phone_number', sa.String(length=20), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'phone_number')
    op.drop_column('users', 'locale')
    op.drop_column('users', 'bio')
