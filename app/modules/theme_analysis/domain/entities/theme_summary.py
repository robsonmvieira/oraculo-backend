"""Entidade para sumário narrativo enriquecido de temas."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from app.modules.shared.infra.database.orm.metadata import Base


class ThemeSummary(Base):
    """
    Sumário narrativo enriquecido de um tema individual.
    Gerado a partir dos dados do Theme 01 e opcionalmente do Theme 02.
    """

    __tablename__ = "theme_summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    theme_id = Column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analysis_id = Column(
        UUID(as_uuid=True),
        ForeignKey("theme_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    narrative = Column(Text, nullable=True)
    highlights = Column(
        JSON, nullable=True
    )  # [{"title": "...", "subreddit": "...", "score": N, "why_notable": "..."}]
    emotional_tone = Column(String(30), nullable=True)
    tone_description = Column(String(200), nullable=True)
    key_themes = Column(
        JSON, nullable=True
    )  # [{"theme": "...", "description": "..."}]
    intent_breakdown = Column(
        JSON, nullable=True
    )  # {"advice_request": N, "pain_and_anger": N, ...}
    week_differentiator = Column(Text, nullable=True)
    fingerprint = Column(String(64), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    theme = relationship("Theme")
    analysis = relationship("ThemeAnalysis")
