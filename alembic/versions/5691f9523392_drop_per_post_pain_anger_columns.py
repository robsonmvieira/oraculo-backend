"""drop per_post pain_anger columns

Revision ID: 5691f9523392
Revises: 21a88f94dc62
Create Date: 2026-02-28 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5691f9523392"
down_revision: Union[str, None] = "21a88f94dc62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(
        op.f("ix_post_intent_classifications_sentiment"),
        table_name="post_intent_classifications",
    )
    op.drop_column("post_intent_classifications", "topic_keyword")
    op.drop_column("post_intent_classifications", "sentiment")


def downgrade() -> None:
    op.add_column(
        "post_intent_classifications",
        sa.Column("sentiment", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "post_intent_classifications",
        sa.Column("topic_keyword", sa.String(length=50), nullable=True),
    )
    op.create_index(
        op.f("ix_post_intent_classifications_sentiment"),
        "post_intent_classifications",
        ["sentiment"],
        unique=False,
    )
