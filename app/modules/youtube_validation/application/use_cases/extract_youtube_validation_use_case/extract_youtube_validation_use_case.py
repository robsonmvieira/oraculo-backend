"""Orchestrates YouTube cross-platform validation: collect, analyze, persist."""

import logging
import os
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.audience_topics.infra.repositories.audience_topic_repository import (
    AudienceTopicRepository,
)
from app.modules.youtube_validation.application.helpers.youtube_context_limits import (
    get_youtube_context_limits,
)
from app.modules.youtube_validation.application.use_cases.extract_youtube_validation_use_case.agent.youtube_validation_agent import (
    create_youtube_validation_agent,
)
from app.modules.youtube_validation.infra.providers.youtube_provider import (
    YouTubeProvider,
)
from app.modules.youtube_validation.infra.repositories.youtube_validation_repository import (
    YouTubeValidationRepository,
)

logger = logging.getLogger(__name__)

_MODEL_ENV = "YOUTUBE_VALIDATION_MODEL_NAME"
_MODEL_FALLBACK_ENV = "MODEL_NAME"
_DEFAULT_MODEL = "gpt-5-nano-2025-08-07"


class ExtractYouTubeValidationUseCase:
    """
    Coleta vídeos YouTube, cruza com dados Reddit e roda análise LLM.
    Pensado para rodar em background thread.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.topic_repo = AudienceTopicRepository(db)
        self.validation_repo = YouTubeValidationRepository(db)
        self.youtube_provider = YouTubeProvider()

    def execute(
        self,
        audience_id: UUID,
        validation_id: UUID,
        user_id: UUID,
        language: str = "en",
    ) -> bool:
        """
        Executa a validação cross-platform completa.

        Args:
            audience_id: ID da audiência
            validation_id: ID da validação já criada (status: processing)
            user_id: ID do usuário que disparou
            language: Idioma preferido do usuário

        Returns:
            True se concluiu com sucesso
        """
        audience = None
        try:
            # 1. Buscar audiência e tópicos
            audience = self.audience_repo.find_by_id(audience_id)
            if not audience:
                self.validation_repo.mark_failed(validation_id, "Audience not found")
                return False

            latest_analysis = self.topic_repo.find_latest_ready(audience_id)
            if not latest_analysis:
                self.validation_repo.mark_failed(
                    validation_id,
                    "No ready topic analysis found",
                )
                return False

            topics = self.topic_repo.get_topics(latest_analysis.id)
            if not topics:
                self.validation_repo.mark_failed(validation_id, "No topics found")
                return False

            limits = get_youtube_context_limits()

            # 2. Coletar dados YouTube por tópico
            logger.info(
                "Collecting YouTube data for %d topics (audience %s)",
                len(topics),
                audience_id,
            )

            topics_youtube_data = []
            all_collected_videos = []

            for topic in topics:
                videos = self.youtube_provider.collect_for_topic(
                    topic_name=topic.name,
                    max_videos=limits.max_videos_per_topic,
                    max_comments_per_video=limits.max_comments_per_video,
                    max_videos_with_transcript=limits.max_videos_with_transcript,
                    max_transcript_chars=limits.max_transcript_chars,
                )

                topics_youtube_data.append(
                    {
                        "topic_name": topic.name,
                        "videos": videos,
                    }
                )

                for v in videos:
                    all_collected_videos.append(
                        {
                            "topic_name": topic.name,
                            "video_id": v.get("video_id", ""),
                            "title": v.get("title"),
                            "channel_name": v.get("channel_name"),
                            "views": v.get("views"),
                            "likes": v.get("likes"),
                            "duration_seconds": v.get("duration_seconds"),
                            "tags": v.get("tags"),
                            "description": v.get("description"),
                            "comments": v.get("comments"),
                            "transcript": v.get("transcript"),
                            "transcript_lang": v.get("transcript_lang"),
                            "published_at": v.get("published_at"),
                        }
                    )

            # 3. Persistir vídeos coletados
            if all_collected_videos:
                self.validation_repo.save_collected_videos(
                    validation_id, all_collected_videos
                )

            total_videos = len(all_collected_videos)
            total_comments = sum(
                len(v.get("comments") or []) for v in all_collected_videos
            )

            logger.info(
                "Collected %d videos with %d comments for audience %s",
                total_videos,
                total_comments,
                audience_id,
            )

            # 4. Preparar dados Reddit dos tópicos
            topics_reddit_data = []
            for topic in topics:
                communities = topic.communities or []
                community_names = [c.get("name", "") for c in communities]

                topics_reddit_data.append(
                    {
                        "topic_name": topic.name,
                        "topic_description": topic.description or "",
                        "post_count": topic.post_count or 0,
                        "avg_score": 0,
                        "community_count": len(communities),
                        "communities": community_names,
                    }
                )

            # 5. Rodar agente LangGraph
            agent = create_youtube_validation_agent()
            result = agent.invoke(
                {
                    "audience_id": str(audience_id),
                    "audience_name": audience.name,
                    "language": language,
                    "topics_reddit_data": topics_reddit_data,
                    "topics_youtube_data": topics_youtube_data,
                    "analysis_result": None,
                    "analysis_summary": None,
                }
            )

            analysis_result = result.get("analysis_result")
            analysis_summary = result.get("analysis_summary")

            if not analysis_result:
                self.validation_repo.mark_failed(
                    validation_id,
                    "LLM analysis returned no results",
                )
                return False

            # 6. Salvar resultado
            model_used = os.getenv(_MODEL_ENV) or os.getenv(
                _MODEL_FALLBACK_ENV, _DEFAULT_MODEL
            )
            self.validation_repo.mark_ready(
                validation_id=validation_id,
                analysis_data=analysis_result,
                summary=analysis_summary or {},
                total_videos=total_videos,
                total_comments=total_comments,
                model_used=model_used,
            )

            # 7. Limpar validações antigas
            self.validation_repo.delete_old_validations(audience_id, keep_latest=2)

            logger.info(
                "YouTube validation complete for audience %s: "
                "%d videos, %d comments analyzed",
                audience_id,
                total_videos,
                total_comments,
            )

            # 8. Avaliar alertas cross-platform
            self._evaluate_alerts(
                audience_id=audience_id,
                validation_id=validation_id,
                user_id=user_id,
                audience_name=audience.name,
                analysis_result=analysis_result,
            )

            # 9. Notificar usuário
            self._notify_complete(
                user_id=user_id,
                audience_id=audience_id,
                audience_name=audience.name,
                validation_id=validation_id,
            )

            return True

        except Exception as e:
            logger.exception("YouTube validation failed for audience %s", audience_id)
            try:
                self.validation_repo.mark_failed(validation_id, str(e))
            except Exception:
                pass
            try:
                self._notify_failed(
                    user_id=user_id,
                    audience_id=audience_id,
                    audience_name=audience.name if audience else "",
                    validation_id=validation_id,
                    error_message=str(e),
                )
            except Exception:
                pass
            return False

    def _notify_complete(
        self,
        user_id: UUID,
        audience_id: UUID,
        audience_name: str,
        validation_id: UUID,
    ) -> None:
        try:
            from app.modules.notifications.application.services.notification_event_service import (
                NotificationEventService,
            )

            NotificationEventService(self.db).notify_analysis_complete(
                user_id=user_id,
                analysis_type="youtube_validation",
                analysis_id=validation_id,
                audience_id=audience_id,
                audience_name=audience_name,
            )
        except Exception:
            logger.debug("Failed to send YouTube validation complete notification")

    def _notify_failed(
        self,
        user_id: UUID,
        audience_id: UUID,
        audience_name: str,
        validation_id: UUID,
        error_message: str,
    ) -> None:
        try:
            from app.modules.notifications.application.services.notification_event_service import (
                NotificationEventService,
            )

            NotificationEventService(self.db).notify_analysis_failed(
                user_id=user_id,
                analysis_type="youtube_validation",
                analysis_id=validation_id,
                audience_id=audience_id,
                audience_name=audience_name,
                error_message=error_message,
            )
        except Exception:
            logger.debug("Failed to send YouTube validation failed notification")

    def _evaluate_alerts(
        self,
        audience_id: UUID,
        validation_id: UUID,
        user_id: UUID,
        audience_name: str,
        analysis_result: dict,
    ) -> None:
        try:
            from app.modules.topic_alerts.application.use_cases.evaluate_alerts_use_case import (
                EvaluateAlertsUseCase,
            )

            EvaluateAlertsUseCase(self.db).evaluate_youtube_validation(
                audience_id=audience_id,
                validation_id=validation_id,
                user_id=user_id,
                audience_name=audience_name,
                analysis_result=analysis_result,
            )
        except Exception:
            logger.debug("Failed to evaluate cross-platform alerts")
