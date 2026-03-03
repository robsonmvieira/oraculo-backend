"""add intent ask and chat tables

Revision ID: d7a1b2c3e4f5
Revises: cc2c9c233554
Create Date: 2026-03-03 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d7a1b2c3e4f5"
down_revision: Union[str, Sequence[str], None] = "cc2c9c233554"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # intent_ask_logs
    op.create_table(
        "intent_ask_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "intent_classification_analyses.id", ondelete="CASCADE"
            ),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "audience_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audiences.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "intent_category",
            sa.String(30),
            nullable=False,
            server_default="pain_and_anger",
        ),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column(
            "context_quality",
            sa.String(20),
            nullable=False,
            server_default="limited",
        ),
        sa.Column(
            "cached", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )

    # intent_conversations
    op.create_table(
        "intent_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "intent_classification_analyses.id", ondelete="CASCADE"
            ),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "audience_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audiences.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "intent_category",
            sa.String(30),
            nullable=False,
            server_default="pain_and_anger",
        ),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column(
            "context_quality",
            sa.String(20),
            nullable=False,
            server_default="limited",
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default="true"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )

    # intent_conversation_messages
    op.create_table(
        "intent_conversation_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intent_conversations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("context_quality", sa.String(20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("intent_conversation_messages")
    op.drop_table("intent_conversations")
    op.drop_table("intent_ask_logs")
