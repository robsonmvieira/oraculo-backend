"""Entidade para dados estruturados do painel de temas."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from app.modules.shared.infra.database.orm.metadata import Base


class ThemePanel(Base):
    """
    Dados estruturados do painel de um tema individual.
    Agrega subcategorias (IA), tópicos relacionados (programático) e distribuição de subreddits.
    """

    __tablename__ = "theme_panels"

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
    subcategories = Column(
        JSON, nullable=True
    )  # [{"name": "Frustration", "count": 15, "description": "..."}]
    related_topics = Column(
        JSON, nullable=True
    )  # [{"name": "Dog", "count": 3, "topic_id": "uuid"}]
    subreddit_distribution = Column(
        JSON, nullable=True
    )  # [{"name": "r/dogbreed", "post_count": 8, "avg_score": 45.2}]
    action_links = Column(
        JSON, nullable=True
    )  # {"view_all": "...", "patterns": "...", "ask": "...", "copy_summary": true}
    fingerprint = Column(String(64), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    theme = relationship("Theme")
    analysis = relationship("ThemeAnalysis")
