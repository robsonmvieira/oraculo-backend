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


class TopicDeepDiveAnalysis(Base):
    """
    Registro de uma análise de deep dive de um tópico.
    Criado sob demanda quando o usuário clica em "Browse All".
    """

    __tablename__ = "topic_deep_dive_analyses"

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

    deep_dive = relationship(
        "TopicDeepDive",
        back_populates="analysis",
        cascade="all, delete-orphan",
        uselist=False,
    )


class TopicDeepDive(Base):
    """
    Resultado do deep dive de um tópico.
    Contém análise profunda: subtópicos, FAQs, sentimento, produtos, insights.
    """

    __tablename__ = "topic_deep_dives"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(
        UUID(as_uuid=True),
        ForeignKey("topic_deep_dive_analyses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    summary = Column(Text, nullable=True)
    subtopics = Column(JSON, nullable=True)
    # [{"name": "...", "description": "...", "post_count": N}]
    common_questions = Column(JSON, nullable=True)
    # [{"question": "...", "frequency": "high|medium|low", "example_context": "..."}]
    sentiment = Column(JSON, nullable=True)
    # {"overall": "positive|negative|neutral|mixed", "positive_ratio": 0.6,
    #  "negative_ratio": 0.2, "neutral_ratio": 0.2,
    #  "highlights": [{"text": "...", "sentiment": "positive", "source": "r/sub"}]}
    mentioned_products = Column(JSON, nullable=True)
    # [{"name": "...", "category": "tool|service|brand", "sentiment": "positive",
    #   "mention_count": N, "context": "..."}]
    representative_posts = Column(JSON, nullable=True)
    # [{"title": "...", "subreddit": "...", "score": N, "permalink": "...", "excerpt": "..."}]
    actionable_insights = Column(JSON, nullable=True)
    # [{"insight": "...", "type": "opportunity|gap|trend|warning", "confidence": "high|medium|low"}]
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    analysis = relationship("TopicDeepDiveAnalysis", back_populates="deep_dive")
