"""Serviço de eventos de notificação — bridge entre background threads e SSE via Redis pub/sub."""

import json
import logging
import os
from uuid import UUID

from redis import Redis
from sqlalchemy.orm import Session

from app.modules.notifications.infra.repositories.notification_repository import (
    NotificationRepository,
)

logger = logging.getLogger(__name__)

# Labels legíveis para cada tipo de análise
_TYPE_LABELS = {
    "topic_analysis": "Topic Analysis",
    "keyword_analysis": "Keyword Analysis",
    "deep_dive": "Deep Dive",
    "pattern_analysis": "Pattern Analysis",
    "behavioral_pattern": "Behavioral Patterns",
    "theme_analysis": "Theme Analysis",
    "intent_classification": "Intent Classification",
    "theme_summary": "Theme Summary",
    "communities_changed": "Communities Update",
    "communities_validation_failed": "Community Validation",
    "youtube_validation": "YouTube Validation",
}


class NotificationEventService:
    """Persiste notificação no banco e publica via Redis pub/sub."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = NotificationRepository(db)
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis = Redis.from_url(redis_url, decode_responses=True)

    def notify(
        self,
        user_id: UUID,
        type_: str,
        title: str,
        message: str,
        metadata: dict | None = None,
    ) -> None:
        """Persiste notificação e publica no Redis pub/sub."""
        notification = self.repo.create(
            user_id=user_id,
            type_=type_,
            title=title,
            message=message,
            metadata=metadata or {},
        )

        channel = f"notifications:{user_id}"
        payload = json.dumps(
            {
                "id": str(notification.id),
                "type": type_,
                "title": title,
                "message": message,
                "metadata": metadata or {},
                "created_at": notification.created_at.isoformat(),
            }
        )

        try:
            self._redis.publish(channel, payload)
        except Exception:
            logger.exception(
                "Failed to publish notification to Redis for user %s", user_id
            )

    def notify_analysis_complete(
        self,
        user_id: UUID,
        analysis_type: str,
        analysis_id: UUID,
        audience_id: UUID,
        audience_name: str,
        topic_id: UUID | None = None,
        topic_name: str | None = None,
    ) -> None:
        """Notificação de análise concluída com sucesso."""
        label = _TYPE_LABELS.get(analysis_type, analysis_type)
        context = (
            f" for topic '{topic_name}'"
            if topic_name
            else f" for audience '{audience_name}'"
        )

        metadata = {
            "audience_id": str(audience_id),
            "analysis_id": str(analysis_id),
            "audience_name": audience_name,
        }
        if topic_id:
            metadata["topic_id"] = str(topic_id)
            metadata["topic_name"] = topic_name

        self.notify(
            user_id=user_id,
            type_=f"{analysis_type}_complete",
            title=f"{label} Ready",
            message=f"{label} analysis{context} is complete.",
            metadata=metadata,
        )

    def notify_analysis_failed(
        self,
        user_id: UUID,
        analysis_type: str,
        analysis_id: UUID,
        audience_id: UUID,
        audience_name: str,
        error_message: str,
        topic_id: UUID | None = None,
        topic_name: str | None = None,
    ) -> None:
        """Notificação de análise que falhou."""
        label = _TYPE_LABELS.get(analysis_type, analysis_type)
        context = (
            f" for topic '{topic_name}'"
            if topic_name
            else f" for audience '{audience_name}'"
        )

        metadata = {
            "audience_id": str(audience_id),
            "analysis_id": str(analysis_id),
            "audience_name": audience_name,
            "error": error_message,
        }
        if topic_id:
            metadata["topic_id"] = str(topic_id)
            metadata["topic_name"] = topic_name

        self.notify(
            user_id=user_id,
            type_=f"{analysis_type}_failed",
            title=f"{label} Failed",
            message=f"{label} analysis{context} failed: {error_message}",
            metadata=metadata,
        )
