"""Entidade de draft de conteudo produzido por plataforma."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from app.modules.shared.infra.database.database import Base


class ContentDraft(Base):
    """Draft de conteudo gerado para uma plataforma especifica."""

    __tablename__ = "content_drafts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    suggestion_id = Column(
        UUID(as_uuid=True),
        ForeignKey("content_suggestions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="processing")

    # Conteudo gerado
    hooks = Column(JSON, nullable=True)
    full_draft = Column(Text, nullable=True)
    narrative_arc = Column(Text, nullable=True)
    cta = Column(Text, nullable=True)
    platform_notes = Column(Text, nullable=True)
    hashtags = Column(JSON, nullable=True)

    # Imagem
    image_url = Column(Text, nullable=True)
    image_aspect_ratio = Column(String(10), nullable=True)

    # Metadata
    model_used = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    suggestion = relationship("ContentSuggestion", back_populates="drafts")
