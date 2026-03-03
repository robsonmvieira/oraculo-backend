import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.modules.shared.infra.database.orm.metadata import Base


class TopicConversation(Base):
    """
    Sessao de chat entre usuario e IA sobre um topico.
    Cada conversa agrupa multiplas mensagens com historico.
    """

    __tablename__ = "topic_conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audience_topics.id", ondelete="CASCADE"),
        nullable=False,
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
        "TopicConversationMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="TopicConversationMessage.created_at",
    )
