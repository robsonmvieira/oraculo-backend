from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.topic_chat.domain.entities.topic_conversation_message import (
    TopicConversationMessage,
)


class TopicConversationMessageRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        context_quality: str | None = None,
    ) -> TopicConversationMessage:
        """Cria uma nova mensagem na conversa."""
        message = TopicConversationMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            context_quality=context_quality,
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def list_by_conversation(
        self, conversation_id: UUID, limit: int = 50
    ) -> list[TopicConversationMessage]:
        """Lista mensagens de uma conversa em ordem cronologica."""
        return (
            self.db.query(TopicConversationMessage)
            .filter(TopicConversationMessage.conversation_id == conversation_id)
            .order_by(TopicConversationMessage.created_at.asc())
            .limit(limit)
            .all()
        )

    def count_by_conversation(self, conversation_id: UUID) -> int:
        """Conta mensagens de uma conversa."""
        return (
            self.db.query(TopicConversationMessage)
            .filter(TopicConversationMessage.conversation_id == conversation_id)
            .count()
        )
