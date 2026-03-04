"""add product intelligence tables

Revision ID: b3c4d5e6f7a8
Revises: 28a8453991e9
Create Date: 2026-03-04 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "28a8453991e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tabela de análises
    op.create_table(
        "product_intelligence_analyses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "audience_id",
            UUID(as_uuid=True),
            sa.ForeignKey("audiences.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="processing",
            index=True,
        ),
        sa.Column("fingerprint", sa.String(64), nullable=False, index=True),
        sa.Column("total_products_found", sa.Integer, nullable=True),
        sa.Column("total_mentions_analyzed", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 2. Tabela de perfis de produtos
    op.create_table(
        "product_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "analysis_id",
            UUID(as_uuid=True),
            sa.ForeignKey("product_intelligence_analyses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("product_name", sa.String(255), nullable=False, index=True),
        sa.Column("normalized_name", sa.String(255), nullable=False, index=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("total_mentions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sentiment_score", sa.Float, nullable=True),
        sa.Column("sentiment_label", sa.String(20), nullable=True),
        sa.Column("trend_direction", sa.String(20), nullable=True),
        sa.Column("positive_aspects", JSON, nullable=True),
        sa.Column("negative_aspects", JSON, nullable=True),
        sa.Column("gaps", JSON, nullable=True),
        sa.Column("alternatives", JSON, nullable=True),
        sa.Column("evidence_quotes", JSON, nullable=True),
        sa.Column("communities", JSON, nullable=True),
        sa.Column("use_cases", JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 3. Tabela de oportunidades de mercado
    op.create_table(
        "product_opportunities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "analysis_id",
            UUID(as_uuid=True),
            sa.ForeignKey("product_intelligence_analyses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("opportunity_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("opportunity_score", sa.Float, nullable=True),
        sa.Column("demand_signals", sa.Integer, nullable=True),
        sa.Column("existing_solutions_count", sa.Integer, nullable=True),
        sa.Column("evidence", JSON, nullable=True),
        sa.Column("related_products", JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("product_opportunities")
    op.drop_table("product_profiles")
    op.drop_table("product_intelligence_analyses")
