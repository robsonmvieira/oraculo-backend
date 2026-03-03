import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.intent_chat.infra.repositories.intent_conversation_repository import (
    IntentConversationRepository,
)
from app.modules.intent_classification.infra.repositories.intent_classification_repository import (
    IntentClassificationRepository,
)

logger = logging.getLogger(__name__)


class StartIntentConversationUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.intent_repo = IntentClassificationRepository(db)
        self.conversation_repo = IntentConversationRepository(db)

    def execute(
        self,
        audience_id: UUID,
        user_id: UUID,
        intent_category: str,
        window: str = "week",
    ) -> dict:
        """
        Cria uma nova conversa sobre uma categoria de intencao.

        Returns:
            dict com conversation_id, intent_category, context_quality, suggestion
        """
        audience = self.audience_repo.find_by_id(audience_id)
        if not audience:
            return {"error": "Audience not found"}

        # Determine context quality
        context_quality = "limited"
        analysis_id = None
        intent_analysis = self.intent_repo.find_latest_by_audience_and_window(
            audience_id, window
        )
        if intent_analysis and intent_analysis.status == "ready":
            analysis_id = intent_analysis.id
            summaries = self.intent_repo.get_intent_summaries(intent_analysis.id)
            has_category = any(s.intent_category == intent_category for s in summaries)
            if has_category:
                context_quality = "rich"

        conversation = self.conversation_repo.create(
            analysis_id=analysis_id,
            audience_id=audience_id,
            user_id=user_id,
            intent_category=intent_category,
            context_quality=context_quality,
        )

        logger.info(
            "Intent Chat: started conversation '%s' for category '%s' (quality: %s)",
            conversation.id,
            intent_category,
            context_quality,
        )

        suggestion = None
        if context_quality == "limited":
            suggestion = (
                "Execute a classificação de intenções para obter respostas "
                "mais detalhadas e baseadas em dados reais."
            )

        return {
            "conversation_id": str(conversation.id),
            "intent_category": intent_category,
            "context_quality": context_quality,
            "suggestion": suggestion,
        }
