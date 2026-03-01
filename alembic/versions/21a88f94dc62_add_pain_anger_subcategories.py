"""add pain_anger_subcategories

Revision ID: 21a88f94dc62
Revises: 768ceb994b1f
Create Date: 2026-02-28 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "21a88f94dc62"
down_revision: Union[str, None] = "768ceb994b1f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "intent_summaries",
        sa.Column("subcategories", sa.JSON(), nullable=True),
    )
    op.add_column(
        "intent_summaries",
        sa.Column("topic_keywords", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("intent_summaries", "topic_keywords")
    op.drop_column("intent_summaries", "subcategories")
