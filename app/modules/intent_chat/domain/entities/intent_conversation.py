import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.modules.shared.infra.database.orm.metadata import Base


class IntentConversation(Base):
    """
    Sessao de chat entre usuario e IA sobre uma categoria de intencao.
    Cada conversa agrupa multiplas mensagens com historico.
    """

    __tablename__ = "intent_conversations"

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
    title = Column(String(255), nullable=True)
    context_quality = Column(
        String(20), nullable=False, default="limited"
    )  # rich, limited
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    messages = relationship(
        "IntentConversationMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="IntentConversationMessage.created_at",
    )
