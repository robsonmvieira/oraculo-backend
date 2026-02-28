"""Entidades para classificação de intenção de posts."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from app.modules.shared.infra.database.orm.metadata import Base


class IntentClassificationAnalysis(Base):
    """Registro de uma análise de classificação de intenção."""

    __tablename__ = "intent_classification_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    theme_analysis_id = Column(
        UUID(as_uuid=True),
        ForeignKey("theme_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    audience_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audiences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(
        String(20), nullable=False, default="processing", index=True
    )  # processing, ready, failed
    time_window = Column(String(10), nullable=False)  # week, month
    fingerprint = Column(String(64), nullable=False, index=True)
    total_posts_classified = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    post_classifications = relationship(
        "PostIntentClassification",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )
    intent_summaries = relationship(
        "IntentSummary",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )


class PostIntentClassification(Base):
    """Classificação de intenção de um post individual."""

    __tablename__ = "post_intent_classifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(
        UUID(as_uuid=True),
        ForeignKey("intent_classification_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    post_reddit_id = Column(String(20), nullable=False)
    post_title = Column(String(500), nullable=False)
    post_subreddit = Column(String(100), nullable=False)
    primary_intent = Column(String(30), nullable=False, index=True)
    secondary_intent = Column(String(30), nullable=True)
    confidence = Column(String(10), nullable=False)  # high, medium, low
    sentiment = Column(String(30), nullable=True, index=True)  # Apenas para pain_and_anger
    topic_keyword = Column(String(50), nullable=True)  # Apenas para pain_and_anger
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    analysis = relationship(
        "IntentClassificationAnalysis", back_populates="post_classifications"
    )


class IntentSummary(Base):
    """Resumo agregado de uma categoria de intenção."""

    __tablename__ = "intent_summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(
        UUID(as_uuid=True),
        ForeignKey("intent_classification_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    intent_category = Column(String(30), nullable=False)
    post_count = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    top_subreddits = Column(JSON, nullable=True)  # [{"name": "sub", "count": N}]
    sample_posts = Column(
        JSON, nullable=True
    )  # [{"title": "...", "subreddit": "...", "score": N}]
    subcategories = Column(JSON, nullable=True)  # {"frustration": 15, "anger": 4, ...}
    topic_keywords = Column(JSON, nullable=True)  # {"dog": 15, "behavior": 8, ...}
    rank = Column(Integer, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    analysis = relationship(
        "IntentClassificationAnalysis", back_populates="intent_summaries"
    )
