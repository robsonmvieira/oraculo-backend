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


class TopicPatternAnalysis(Base):
    """
    Registro de uma analise de padroes cross-topic de uma audiencia.
    Criado sob demanda quando o usuario clica em "Patterns".
    """

    __tablename__ = "topic_pattern_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audience_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audiences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(
        String(20), nullable=False, default="processing", index=True
    )  # processing, ready, failed
    communities_fingerprint = Column(String(64), nullable=False, index=True)
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

    pattern = relationship(
        "TopicPattern",
        back_populates="analysis",
        cascade="all, delete-orphan",
        uselist=False,
    )


class TopicPattern(Base):
    """
    Resultado da deteccao de padroes cross-topic.
    Contem co-ocorrencias, perguntas sem resposta, gaps e oportunidades.
    """

    __tablename__ = "topic_patterns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(
        UUID(as_uuid=True),
        ForeignKey("topic_pattern_analyses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    summary = Column(Text, nullable=True)
    co_occurrences = Column(JSON, nullable=True)
    # [{"topics": ["A", "B"], "frequency": "high", "context": "..."}]
    unanswered_questions = Column(JSON, nullable=True)
    # [{"question": "...", "frequency": "high", "communities": ["r/..."], "opportunity": "..."}]
    cross_community_gaps = Column(JSON, nullable=True)
    # [{"topic": "...", "discussed_in": ["r/..."], "missing_in": ["r/..."], "opportunity": "..."}]
    content_opportunities = Column(JSON, nullable=True)
    # [{"opportunity": "...", "type": "content|product|service", "confidence": "high|medium|low", "based_on": "..."}]
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    analysis = relationship("TopicPatternAnalysis", back_populates="pattern")
