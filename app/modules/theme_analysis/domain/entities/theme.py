"""Entidades do módulo de análise temporal de temas."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship

from app.modules.shared.infra.database.orm.metadata import Base


class ThemeAnalysis(Base):
    """
    Registro de uma análise temporal de temas de uma audiência.
    Cada análise é associada a uma janela temporal (week ou month).
    """

    __tablename__ = "theme_analyses"

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
    time_window = Column(
        String(10), nullable=False, index=True
    )  # week, month
    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=True)
    communities_fingerprint = Column(String(64), nullable=False, index=True)
    total_themes = Column(Integer, nullable=True)
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

    themes = relationship(
        "Theme",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )


class Theme(Base):
    """Tema extraído de uma análise temporal."""

    __tablename__ = "themes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(
        UUID(as_uuid=True),
        ForeignKey("theme_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(200), nullable=False)
    summary = Column(Text, nullable=True)
    post_count = Column(Integer, nullable=True)
    avg_score = Column(Float, nullable=True)
    avg_comments = Column(Float, nullable=True)
    engagement_score = Column(Float, nullable=True)
    top_subreddits = Column(JSON, nullable=True)  # [{"name": "sub", "post_count": N, "avg_score": N}]
    top_keywords = Column(JSON, nullable=True)  # [{"keyword": "...", "frequency": N}]
    representative_posts = Column(JSON, nullable=True)  # [{"title": "...", "subreddit": "...", "score": N, "permalink": "..."}]
    rank = Column(Integer, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    analysis = relationship("ThemeAnalysis", back_populates="themes")
