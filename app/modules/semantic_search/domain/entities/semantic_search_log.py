import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.modules.shared.infra.database.orm.metadata import Base


class SemanticSearchLog(Base):
    """Log de buscas semânticas para analytics."""

    __tablename__ = "semantic_search_logs"

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
    query = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)
    total_posts_searched = Column(Integer, nullable=True)
    total_posts_matched = Column(Integer, nullable=True)
    pattern_count = Column(Integer, nullable=True)
    context_quality = Column(String(20), nullable=False, default="limited")
    cached = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
