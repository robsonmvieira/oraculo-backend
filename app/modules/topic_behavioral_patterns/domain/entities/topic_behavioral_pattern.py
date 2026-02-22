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


class TopicBehavioralPatternAnalysis(Base):
    """
    Registro de uma análise de padrões comportamentais de um tópico.
    Criado sob demanda quando o usuário clica em "Patterns" no tópico.
    """

    __tablename__ = "topic_behavioral_pattern_analyses"

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

    behavioral_pattern = relationship(
        "TopicBehavioralPattern",
        back_populates="analysis",
        cascade="all, delete-orphan",
        uselist=False,
    )


class TopicBehavioralPattern(Base):
    """
    Resultado da análise de padrões comportamentais de um tópico.
    Contém: tool_patterns, workaround_patterns, friction_patterns,
    shift_patterns, demand_signals.
    """

    __tablename__ = "topic_behavioral_patterns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(
        UUID(as_uuid=True),
        ForeignKey("topic_behavioral_pattern_analyses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    summary = Column(Text, nullable=True)
    tool_patterns = Column(JSON, nullable=True)
    # [{"tool": "...", "use_case": "...", "satisfaction": "...", "evidence": "..."}]
    workaround_patterns = Column(JSON, nullable=True)
    # [{"problem": "...", "workaround": "...", "frequency": "...", "evidence": "..."}]
    friction_patterns = Column(JSON, nullable=True)
    # [{"friction": "...", "category": "...", "severity": "...", "evidence": "..."}]
    shift_patterns = Column(JSON, nullable=True)
    # [{"from": "...", "to": "...", "reason": "...", "evidence": "..."}]
    demand_signals = Column(JSON, nullable=True)
    # [{"signal": "...", "frequency": "...", "communities": [...], "evidence": "..."}]
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    analysis = relationship("TopicBehavioralPatternAnalysis", back_populates="behavioral_pattern")
