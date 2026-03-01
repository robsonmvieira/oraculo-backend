"""drop top_subreddits from intent_summaries

Revision ID: 7a65e81501c8
Revises: 5691f9523392
Create Date: 2026-02-28 17:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7a65e81501c8"
down_revision: Union[str, None] = "5691f9523392"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("intent_summaries", "top_subreddits")


def downgrade() -> None:
    op.add_column(
        "intent_summaries",
        sa.Column("top_subreddits", sa.JSON(), nullable=True),
    )
