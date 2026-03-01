"""Entidades de sugestões inteligentes de conteúdo."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from app.modules.shared.infra.database.database import Base


class ContentSuggestionAnalysis(Base):
    """Metadata de uma execução de geração de sugestões de conteúdo."""

    __tablename__ = "content_suggestion_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audience_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audiences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(20), nullable=False, default="processing")
    fingerprint = Column(String(64), nullable=False, index=True)
    modules_used = Column(JSON, nullable=True)
    model_used = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at = Column(DateTime, nullable=True)

    suggestions = relationship(
        "ContentSuggestion",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("audience_id", "fingerprint", name="uq_cs_audience_fingerprint"),
    )


class ContentSuggestion(Base):
    """Sugestão individual de conteúdo gerada pelo agente."""

    __tablename__ = "content_suggestions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(
        UUID(as_uuid=True),
        ForeignKey("content_suggestion_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rank = Column(Integer, nullable=False)
    priority = Column(String(10), nullable=False)
    title = Column(String(500), nullable=False)
    approach = Column(Text, nullable=False)
    why_now = Column(Text, nullable=False)
    evidence = Column(JSON, nullable=True)
    format = Column(String(30), nullable=False)
    format_rationale = Column(Text, nullable=True)
    emotional_tone = Column(String(30), nullable=False)
    tone_rationale = Column(Text, nullable=True)
    outline = Column(JSON, nullable=True)
    keywords = Column(JSON, nullable=True)
    research_notes = Column(Text, nullable=True)
    image_prompt = Column(Text, nullable=True)
    differentiation_notes = Column(Text, nullable=True)
    accuracy_notes = Column(Text, nullable=True)
    source_topics = Column(JSON, nullable=True)
    source_modules = Column(JSON, nullable=True)
    feedback_status = Column(String(20), nullable=True)
    feedback_at = Column(DateTime, nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    analysis = relationship(
        "ContentSuggestionAnalysis", back_populates="suggestions"
    )
