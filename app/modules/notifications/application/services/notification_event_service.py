"""Serviço de eventos de notificação — bridge entre background threads e SSE via Redis pub/sub."""

import json
import logging
import os
from uuid import UUID

from redis import Redis
from sqlalchemy.orm import Session

from app.modules.identity.domain.entities.user import User
from app.modules.notifications.application.services.notification_messages import t
from app.modules.notifications.infra.repositories.notification_repository import (
    NotificationRepository,
)

logger = logging.getLogger(__name__)


class NotificationEventService:
    """Persiste notificação no banco e publica via Redis pub/sub."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = NotificationRepository(db)
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis = Redis.from_url(redis_url, decode_responses=True)

    # ── helpers ──────────────────────────────────────────────

    def _get_user_language(self, user_id: UUID) -> str:
        """Retorna o idioma preferido do usuário ou 'en' como fallback."""
        try:
            user = self.db.query(User.preferred_language).filter_by(id=user_id).first()
            return user[0] if user and user[0] else "en"
        except Exception:
            logger.debug(
                "Could not fetch language for user %s, defaulting to en", user_id
            )
            return "en"

    # ── core ─────────────────────────────────────────────────

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

    # ── analysis complete / failed ───────────────────────────

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
        lang = self._get_user_language(user_id)

        if topic_name:
            msg_key = f"{analysis_type}_complete_msg_topic"
            msg = t(msg_key, lang, topic_name=topic_name)
        else:
            msg_key = f"{analysis_type}_complete_msg_audience"
            msg = t(msg_key, lang, audience_name=audience_name)

        title = t(f"{analysis_type}_complete_title", lang)

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
            title=title,
            message=msg,
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
        lang = self._get_user_language(user_id)

        if topic_name:
            msg_key = f"{analysis_type}_failed_msg_topic"
            msg = t(msg_key, lang, topic_name=topic_name)
        else:
            msg_key = f"{analysis_type}_failed_msg_audience"
            msg = t(msg_key, lang, audience_name=audience_name)

        title = t(f"{analysis_type}_failed_title", lang)

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
            title=title,
            message=msg,
            metadata=metadata,
        )

    # ── communities ──────────────────────────────────────────

    def notify_communities_updated(
        self,
        user_id: UUID,
        audience_id: UUID,
        added: list[str],
        removed: list[str],
    ) -> None:
        """Notificação de comunidades atualizadas na audiência."""
        lang = self._get_user_language(user_id)

        self.notify(
            user_id=user_id,
            type_="communities_changed",
            title=t("communities_updated_title", lang),
            message=t(
                "communities_updated_msg",
                lang,
                added=len(added),
                removed=len(removed),
            ),
            metadata={
                "audience_id": str(audience_id),
                "added": sorted(added),
                "removed": sorted(removed),
            },
        )

    def notify_communities_invalid(
        self,
        user_id: UUID,
        audience_id: UUID,
        invalid_names: list[str],
    ) -> None:
        """Notificação de comunidades inválidas removidas."""
        lang = self._get_user_language(user_id)

        self.notify(
            user_id=user_id,
            type_="communities_validation_failed",
            title=t("communities_invalid_title", lang),
            message=t(
                "communities_invalid_msg",
                lang,
                names=", ".join(invalid_names),
            ),
            metadata={
                "audience_id": str(audience_id),
                "invalid_names": invalid_names,
            },
        )

    # ── content suggestions ──────────────────────────────────

    def notify_content_suggestions_ready(
        self,
        user_id: UUID,
        audience_id: UUID,
        audience_name: str,
        analysis_id: UUID,
        suggestion_count: int,
        metadata_extra: dict | None = None,
    ) -> None:
        """Notificação de sugestões de conteúdo prontas."""
        lang = self._get_user_language(user_id)

        meta = {
            "audience_id": str(audience_id),
            "analysis_id": str(analysis_id),
            "suggestion_count": suggestion_count,
        }
        if metadata_extra:
            meta.update(metadata_extra)

        self.notify(
            user_id=user_id,
            type_="content_suggestions_ready",
            title=t("content_suggestions_ready_title", lang),
            message=t(
                "content_suggestions_ready_msg",
                lang,
                count=suggestion_count,
                audience_name=audience_name,
            ),
            metadata=meta,
        )

    def notify_content_suggestions_failed(
        self,
        user_id: UUID,
        audience_id: UUID,
        audience_name: str,
        analysis_id: UUID,
        error: str,
    ) -> None:
        """Notificação de falha nas sugestões de conteúdo."""
        lang = self._get_user_language(user_id)

        self.notify(
            user_id=user_id,
            type_="content_suggestions_failed",
            title=t("content_suggestions_failed_title", lang),
            message=t(
                "content_suggestions_failed_msg",
                lang,
                audience_name=audience_name,
            ),
            metadata={
                "audience_id": str(audience_id),
                "analysis_id": str(analysis_id),
                "error": error,
            },
        )

    # ── content production ───────────────────────────────────

    def notify_content_production_ready(
        self,
        user_id: UUID,
        audience_id: UUID,
        suggestion_id: UUID,
        suggestion_title: str,
        platforms: list[str],
        draft_count: int,
        has_image: bool = False,
    ) -> None:
        """Notificação de conteúdo produzido com sucesso."""
        lang = self._get_user_language(user_id)

        self.notify(
            user_id=user_id,
            type_="content_production_ready",
            title=t("content_production_ready_title", lang),
            message=t(
                "content_production_ready_msg",
                lang,
                title=suggestion_title[:80],
                platforms=", ".join(platforms),
            ),
            metadata={
                "audience_id": str(audience_id),
                "suggestion_id": str(suggestion_id),
                "platforms": platforms,
                "draft_count": draft_count,
                "has_image": has_image,
            },
        )

    def notify_content_production_failed(
        self,
        user_id: UUID,
        suggestion_id: UUID,
        error: str,
    ) -> None:
        """Notificação de falha na produção de conteúdo."""
        lang = self._get_user_language(user_id)

        self.notify(
            user_id=user_id,
            type_="content_production_failed",
            title=t("content_production_failed_title", lang),
            message=t("content_production_failed_msg", lang),
            metadata={
                "suggestion_id": str(suggestion_id),
                "error": error,
            },
        )
