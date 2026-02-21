import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.modules.shared.infra.database.orm.metadata import Base


class AudienceKeywordAnalysis(Base):
    """
    Registro de uma análise de keywords de uma audiência.
    Cada vez que as comunidades mudam, uma nova análise é criada.
    """

    __tablename__ = "audience_keyword_analyses"

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
    total_keywords = Column(Integer, nullable=True)
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

    keywords = relationship(
        "AudienceKeyword",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )


class AudienceKeyword(Base):
    """
    Palavra-chave de busca extraída para uma audiência.
    """

    __tablename__ = "audience_keywords"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audience_keyword_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    keyword = Column(String(200), nullable=False)
    category = Column(String(50), nullable=True)  # pain_point, question, recommendation, trend, general
    relevance_score = Column(Integer, nullable=True)  # 1-10
    rank = Column(Integer, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    analysis = relationship("AudienceKeywordAnalysis", back_populates="keywords")
