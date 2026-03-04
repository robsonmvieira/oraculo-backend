"""Entidades do módulo Product Intelligence."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from app.modules.shared.infra.database.orm.metadata import Base


class ProductIntelligenceAnalysis(Base):
    """Registro de uma análise de product intelligence de uma audiência."""

    __tablename__ = "product_intelligence_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audience_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audiences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(20), nullable=False, default="processing", index=True)
    fingerprint = Column(String(64), nullable=False, index=True)
    total_products_found = Column(Integer, nullable=True)
    total_mentions_analyzed = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    product_profiles = relationship(
        "ProductProfile",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )
    product_opportunities = relationship(
        "ProductOpportunity",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )


class ProductProfile(Base):
    """Perfil de um produto/ferramenta detectado na audiência."""

    __tablename__ = "product_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(
        UUID(as_uuid=True),
        ForeignKey("product_intelligence_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_name = Column(String(255), nullable=False, index=True)
    normalized_name = Column(String(255), nullable=False, index=True)
    category = Column(String(50), nullable=False)
    total_mentions = Column(Integer, nullable=False, default=0)
    sentiment_score = Column(Float, nullable=True)
    sentiment_label = Column(String(20), nullable=True)
    trend_direction = Column(String(20), nullable=True)
    positive_aspects = Column(JSON, nullable=True)
    negative_aspects = Column(JSON, nullable=True)
    gaps = Column(JSON, nullable=True)
    alternatives = Column(JSON, nullable=True)
    evidence_quotes = Column(JSON, nullable=True)
    communities = Column(JSON, nullable=True)
    use_cases = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    analysis = relationship(
        "ProductIntelligenceAnalysis", back_populates="product_profiles"
    )


class ProductOpportunity(Base):
    """Oportunidade de mercado detectada a partir da análise de produtos."""

    __tablename__ = "product_opportunities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(
        UUID(as_uuid=True),
        ForeignKey("product_intelligence_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    opportunity_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    opportunity_score = Column(Float, nullable=True)
    demand_signals = Column(Integer, nullable=True)
    existing_solutions_count = Column(Integer, nullable=True)
    evidence = Column(JSON, nullable=True)
    related_products = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    analysis = relationship(
        "ProductIntelligenceAnalysis",
        back_populates="product_opportunities",
    )
