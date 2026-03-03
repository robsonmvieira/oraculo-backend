import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID

from app.modules.shared.infra.database.orm.metadata import Base


class IntentAskLog(Base):
    """
    Log de perguntas e respostas do Q&A de intencoes (pain_and_anger, etc).
    Persiste historico para analytics futuros.
    """

    __tablename__ = "intent_ask_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(
        UUID(as_uuid=True),
        ForeignKey("intent_classification_analyses.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
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
    intent_category = Column(String(30), nullable=False, default="pain_and_anger")
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)
    context_quality = Column(
        String(20), nullable=False, default="limited"
    )  # rich, limited
    cached = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
