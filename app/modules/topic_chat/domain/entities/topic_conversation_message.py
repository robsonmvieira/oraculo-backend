import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.modules.shared.infra.database.orm.metadata import Base


class TopicConversationMessage(Base):
    """
    Mensagem individual dentro de uma conversa de chat.
    Pode ser do usuario (role=user) ou da IA (role=assistant).
    """

    __tablename__ = "topic_conversation_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("topic_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    context_quality = Column(
        String(20), nullable=True
    )  # rich, limited (only for assistant messages)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    conversation = relationship(
        "TopicConversation",
        back_populates="messages",
    )
