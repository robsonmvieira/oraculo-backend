import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from app.modules.shared.infra.database.orm.metadata import Base


class AudienceTopicAnalysis(Base):
    """
    Registro de uma análise de tópicos de uma audiência.
    Cada vez que as comunidades mudam, uma nova análise é criada.
    """

    __tablename__ = "audience_topic_analyses"

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
    communities_fingerprint = Column(String(64), nullable=False, index=True)
    total_topics = Column(Integer, nullable=True)
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

    topics = relationship(
        "AudienceTopic",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )


class AudienceTopic(Base):
    """
    Tópico extraído de uma análise de audiência.
    """

    __tablename__ = "audience_topics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audience_topic_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    growth_percentage = Column(Float, nullable=True)
    mention_frequency = Column(Float, nullable=True)
    mention_period = Column(String(10), nullable=True)  # day, week, month
    post_count = Column(Integer, nullable=True)
    communities = Column(JSON, nullable=True)  # [{"name": "sub", "post_count": 5}]
    rank = Column(Integer, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    analysis = relationship("AudienceTopicAnalysis", back_populates="topics")
