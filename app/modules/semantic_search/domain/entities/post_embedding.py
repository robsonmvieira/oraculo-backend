import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID

from app.modules.shared.infra.database.orm.metadata import Base


class PostEmbedding(Base):
    """
    Stores post embeddings for semantic similarity search.
    Uses OpenAI text-embedding-3-small (1536 dimensions).
    One embedding per unique post_reddit_id.
    """

    __tablename__ = "post_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_reddit_id = Column(String(20), nullable=False, unique=True, index=True)
    subreddit = Column(String(100), nullable=False)
    title = Column(String(500), nullable=False)
    selftext_hash = Column(String(64), nullable=True)
    embedding = Column(Vector(1536), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
