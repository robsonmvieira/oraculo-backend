"""Community embedding entity for vector similarity search."""

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.modules.shared.infra.database.orm.metadata import Base


class CommunityEmbedding(Base):
    """
    Stores community embeddings for semantic similarity search.
    Uses OpenAI text-embedding-3-small (1536 dimensions).
    """

    __tablename__ = "community_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subreddit_name = Column(String(100), nullable=False, unique=True, index=True)
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    embedding = Column(Vector(1536), nullable=True)
    subscribers = Column(Integer, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def get_text_for_embedding(self) -> str:
        """Returns the text to be used for generating embedding."""
        parts = []
        if self.title:
            parts.append(self.title)
        if self.description:
            parts.append(self.description)
        if not parts:
            parts.append(self.subreddit_name)
        return " ".join(parts)

    def needs_embedding_update(self, new_title: str | None, new_description: str | None) -> bool:
        """Check if embedding needs to be regenerated due to content change."""
        if self.embedding is None:
            return True
        return self.title != new_title or self.description != new_description
