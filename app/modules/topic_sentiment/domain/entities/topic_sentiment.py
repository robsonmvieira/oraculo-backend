import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from app.modules.shared.infra.database.orm.metadata import Base


class TopicSentimentAnalysis(Base):
    """
    Registro de uma análise de sentimento de um tópico.
    Criado sob demanda quando o usuário clica em "Sentimento".
    """

    __tablename__ = "topic_sentiment_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audience_topics.id", ondelete="CASCADE"),
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
    topic_fingerprint = Column(String(64), nullable=False, index=True)
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

    sentiment = relationship(
        "TopicSentiment",
        back_populates="analysis",
        cascade="all, delete-orphan",
        uselist=False,
    )


class TopicSentiment(Base):
    """
    Resultado da análise de sentimento de um tópico.
    Contém análise emocional profunda: drivers, tensões, dores, oportunidades.
    """

    __tablename__ = "topic_sentiments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(
        UUID(as_uuid=True),
        ForeignKey("topic_sentiment_analyses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    overall_sentiment = Column(JSON, nullable=True)
    # {"score": "positive|negative|neutral|mixed", "positive_ratio": 0.45,
    #  "negative_ratio": 0.25, "neutral_ratio": 0.30}
    emotional_map = Column(JSON, nullable=True)
    # [{"emotion": "enthusiasm", "intensity": "high|medium|low", "percentage": 0.30, "example": "..."}]
    sentiment_by_community = Column(JSON, nullable=True)
    # [{"community": "r/...", "positive": 0.55, "negative": 0.15, "neutral": 0.30, "dominant_emotion": "..."}]
    sentiment_by_subtopic = Column(JSON, nullable=True)
    # [{"subtopic": "...", "sentiment": "positive", "score": 0.72, "key_driver": "..."}]
    sentiment_drivers = Column(JSON, nullable=True)
    # {"positive": [{"driver": "...", "frequency": "high", "mentions": N, "example_quote": "..."}],
    #  "negative": [...]}
    tension_points = Column(JSON, nullable=True)
    # [{"topic": "...", "for_ratio": 0.45, "against_ratio": 0.55, "intensity": "high", "summary": "..."}]
    pain_points = Column(JSON, nullable=True)
    # [{"pain": "...", "severity": "high", "frequency": "medium", "communities": [...], "verbatim": "..."}]
    sentiment_opportunities = Column(JSON, nullable=True)
    # [{"opportunity": "...", "based_on": "...", "confidence": "high", "target_audience": "..."}]
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    analysis = relationship("TopicSentimentAnalysis", back_populates="sentiment")
