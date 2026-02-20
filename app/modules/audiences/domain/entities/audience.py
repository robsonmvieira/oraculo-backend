import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.modules.shared.infra.database.orm.metadata import Base


class Audience(Base):
    """
    Audiência criada pelo usuário.
    Agrupa múltiplas comunidades do Reddit.
    """

    __tablename__ = "audiences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relacionamento com comunidades
    communities = relationship(
        "AudienceCommunity",
        back_populates="audience",
        cascade="all, delete-orphan",
    )


class AudienceCommunity(Base):
    """
    Comunidade dentro de uma audiência.
    """

    __tablename__ = "audience_communities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audience_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audiences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subreddit_name = Column(String(100), nullable=False, index=True)
    added_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relacionamento com audiência
    audience = relationship("Audience", back_populates="communities")
