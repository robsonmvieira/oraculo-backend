import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audience_topics.infra.repositories.audience_topic_repository import (
    AudienceTopicRepository,
)
from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.topic_chat.infra.repositories.topic_conversation_repository import (
    TopicConversationRepository,
)
from app.modules.topic_deep_dive.infra.repositories.topic_deep_dive_repository import (
    TopicDeepDiveRepository,
)

logger = logging.getLogger(__name__)


class StartConversationUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.topic_repo = AudienceTopicRepository(db)
        self.deep_dive_repo = TopicDeepDiveRepository(db)
        self.conversation_repo = TopicConversationRepository(db)

    def execute(
        self,
        topic_id: UUID,
        audience_id: UUID,
        user_id: UUID,
    ) -> dict:
        """
        Cria uma nova conversa sobre um topico.

        Returns:
            dict com conversation_id, topic_name, context_quality
        """
        topic = self.topic_repo.get_topic_by_id(topic_id)
        if not topic:
            return {"error": "Topic not found"}

        audience = self.audience_repo.find_by_id(audience_id)
        if not audience:
            return {"error": "Audience not found"}

        # Determine context quality
        context_quality = "limited"
        latest_analysis = self.deep_dive_repo.find_latest_by_topic(topic_id)
        if latest_analysis and latest_analysis.status == "ready":
            deep_dive = self.deep_dive_repo.get_deep_dive(latest_analysis.id)
            if deep_dive:
                context_quality = "rich"

        conversation = self.conversation_repo.create(
            topic_id=topic_id,
            audience_id=audience_id,
            user_id=user_id,
            context_quality=context_quality,
        )

        logger.info(
            "Topic Chat: started conversation '%s' for topic '%s' (quality: %s)",
            conversation.id,
            topic.name,
            context_quality,
        )

        suggestion = None
        if context_quality == "limited":
            suggestion = (
                "Execute o Deep Dive neste topico para obter respostas "
                "mais detalhadas e baseadas em dados reais."
            )

        return {
            "conversation_id": str(conversation.id),
            "topic_name": topic.name,
            "context_quality": context_quality,
            "suggestion": suggestion,
        }
