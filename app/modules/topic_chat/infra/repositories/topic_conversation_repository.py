from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.topic_chat.domain.entities.topic_conversation import TopicConversation


class TopicConversationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        topic_id: UUID,
        audience_id: UUID,
        user_id: UUID,
        title: str | None = None,
        context_quality: str = "limited",
    ) -> TopicConversation:
        """Cria uma nova conversa."""
        conversation = TopicConversation(
            topic_id=topic_id,
            audience_id=audience_id,
            user_id=user_id,
            title=title,
            context_quality=context_quality,
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def find_by_id(self, conversation_id: UUID) -> TopicConversation | None:
        """Busca conversa por ID."""
        return (
            self.db.query(TopicConversation)
            .filter(TopicConversation.id == conversation_id)
            .first()
        )

    def list_by_topic_and_user(
        self, topic_id: UUID, user_id: UUID, limit: int = 20
    ) -> list[TopicConversation]:
        """Lista conversas de um usuario em um topico, mais recentes primeiro."""
        return (
            self.db.query(TopicConversation)
            .filter(
                TopicConversation.topic_id == topic_id,
                TopicConversation.user_id == user_id,
            )
            .order_by(TopicConversation.updated_at.desc())
            .limit(limit)
            .all()
        )

    def update_title(
        self, conversation_id: UUID, title: str
    ) -> TopicConversation | None:
        """Atualiza o titulo da conversa."""
        conversation = self.find_by_id(conversation_id)
        if conversation:
            conversation.title = title
            conversation.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(conversation)
        return conversation

    def update_context_quality(
        self, conversation_id: UUID, context_quality: str
    ) -> None:
        """Atualiza a qualidade do contexto da conversa."""
        conversation = self.find_by_id(conversation_id)
        if conversation:
            conversation.context_quality = context_quality
            self.db.commit()

    def touch(self, conversation_id: UUID) -> None:
        """Atualiza o updated_at da conversa."""
        conversation = self.find_by_id(conversation_id)
        if conversation:
            conversation.updated_at = datetime.now(timezone.utc)
            self.db.commit()

    def deactivate(self, conversation_id: UUID) -> TopicConversation | None:
        """Desativa uma conversa (soft delete)."""
        conversation = self.find_by_id(conversation_id)
        if conversation:
            conversation.is_active = False
            conversation.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(conversation)
        return conversation
