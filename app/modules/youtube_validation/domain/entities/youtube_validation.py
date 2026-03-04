import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from app.modules.shared.infra.database.orm.metadata import Base


class YouTubeValidation(Base):
    """
    Registro de uma validação cross-platform YouTube para uma audiência.
    Criado quando o usuário dispara a análise YouTube Validation.
    """

    __tablename__ = "youtube_validations"

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
    status = Column(
        String(20), nullable=False, default="processing", index=True
    )  # processing, ready, failed
    fingerprint = Column(String(64), nullable=False, index=True)
    analysis_data = Column(JSON, nullable=True)  # resultado completo da análise LLM
    summary = Column(JSON, nullable=True)  # resumo executivo
    total_videos = Column(Integer, nullable=True, default=0)
    total_comments = Column(Integer, nullable=True, default=0)
    model_used = Column(String(100), nullable=True)
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

    collected_videos = relationship(
        "YouTubeCollectedVideo",
        back_populates="validation",
        cascade="all, delete-orphan",
    )


class YouTubeCollectedVideo(Base):
    """
    Vídeo coletado do YouTube durante a validação cross-platform.
    Persiste metadados, comentários e transcrições para re-análise futura.
    """

    __tablename__ = "youtube_collected_videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    validation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("youtube_validations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_name = Column(String(255), nullable=False)
    video_id = Column(String(20), nullable=False)
    title = Column(Text, nullable=True)
    channel_name = Column(Text, nullable=True)
    views = Column(Integer, nullable=True)
    likes = Column(Integer, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    tags = Column(JSON, nullable=True)
    description = Column(Text, nullable=True)
    comments = Column(JSON, nullable=True)  # [{author, text, likes, published_at}]
    transcript = Column(Text, nullable=True)
    transcript_lang = Column(String(10), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    collected_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    validation = relationship("YouTubeValidation", back_populates="collected_videos")

    __table_args__ = (
        Index("ix_yt_collected_validation_topic", "validation_id", "topic_name"),
        Index(
            "ix_yt_collected_unique",
            "validation_id",
            "video_id",
            unique=True,
        ),
    )
