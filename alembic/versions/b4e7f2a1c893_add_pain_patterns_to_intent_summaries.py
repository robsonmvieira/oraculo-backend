"""add_pain_patterns_to_intent_summaries

Revision ID: b4e7f2a1c893
Revises: cdf0ccae0876
Create Date: 2026-03-02 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b4e7f2a1c893'
down_revision: Union[str, Sequence[str], None] = 'cdf0ccae0876'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('intent_summaries', sa.Column('pain_patterns', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('intent_summaries', 'pain_patterns')
