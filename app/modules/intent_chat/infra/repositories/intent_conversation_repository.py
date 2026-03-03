from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.intent_chat.domain.entities.intent_conversation import (
    IntentConversation,
)


class IntentConversationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        analysis_id: UUID | None,
        audience_id: UUID,
        user_id: UUID,
        intent_category: str,
        title: str | None = None,
        context_quality: str = "limited",
    ) -> IntentConversation:
        """Cria uma nova conversa."""
        conversation = IntentConversation(
            analysis_id=analysis_id,
            audience_id=audience_id,
            user_id=user_id,
            intent_category=intent_category,
            title=title,
            context_quality=context_quality,
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def find_by_id(self, conversation_id: UUID) -> IntentConversation | None:
        """Busca conversa por ID."""
        return (
            self.db.query(IntentConversation)
            .filter(IntentConversation.id == conversation_id)
            .first()
        )

    def list_by_audience_category_and_user(
        self,
        audience_id: UUID,
        intent_category: str,
        user_id: UUID,
        limit: int = 20,
    ) -> list[IntentConversation]:
        """Lista conversas de um usuario para uma audiencia e categoria."""
        return (
            self.db.query(IntentConversation)
            .filter(
                IntentConversation.audience_id == audience_id,
                IntentConversation.intent_category == intent_category,
                IntentConversation.user_id == user_id,
            )
            .order_by(IntentConversation.updated_at.desc())
            .limit(limit)
            .all()
        )

    def update_title(
        self, conversation_id: UUID, title: str
    ) -> IntentConversation | None:
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

    def deactivate(self, conversation_id: UUID) -> IntentConversation | None:
        """Desativa uma conversa (soft delete)."""
        conversation = self.find_by_id(conversation_id)
        if conversation:
            conversation.is_active = False
            conversation.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(conversation)
        return conversation
