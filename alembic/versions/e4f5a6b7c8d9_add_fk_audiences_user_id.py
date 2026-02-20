"""add FK audiences.user_id -> users.id and set NOT NULL

Revision ID: e4f5a6b7c8d9
Revises: d311c4623083
Create Date: 2026-02-20 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, Sequence[str], None] = 'd311c4623083'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Remover audiências órfãs (user_id NULL) que não podem ser vinculadas
    op.execute("DELETE FROM audiences WHERE user_id IS NULL")

    # 2. Tornar user_id NOT NULL
    op.alter_column(
        'audiences',
        'user_id',
        existing_type=sa.UUID(),
        nullable=False,
    )

    # 3. Adicionar FK para users.id
    op.create_foreign_key(
        'fk_audiences_user_id',
        'audiences',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_audiences_user_id', 'audiences', type_='foreignkey')
    op.alter_column(
        'audiences',
        'user_id',
        existing_type=sa.UUID(),
        nullable=True,
    )
