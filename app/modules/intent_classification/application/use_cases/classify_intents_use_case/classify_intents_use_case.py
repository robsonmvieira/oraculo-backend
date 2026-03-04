"""Use case para classificação de intenção de posts."""

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.intent_classification.application.use_cases.classify_intents_use_case.agent.intent_agent import (
    create_intent_classification_agent,
)
from app.modules.intent_classification.infra.repositories.intent_classification_repository import (
    IntentClassificationRepository,
)
from app.modules.theme_analysis.infra.repositories.theme_analysis_repository import (
    ThemeAnalysisRepository,
)
from app.modules.topics.infra.providers.reddit_provider.generic_reddit_provider import (
    GenericRedditProvider,
)

logger = logging.getLogger(__name__)


class ClassifyIntentsUseCase:
    """
    Classifica posts de uma theme_analysis por intenção do autor.
    Pensado para rodar em background thread.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.theme_repo = ThemeAnalysisRepository(db)
        self.intent_repo = IntentClassificationRepository(db)
        self.reddit_provider = GenericRedditProvider()

    def execute(
        self,
        audience_id: UUID,
        analysis_id: UUID,
        theme_analysis_id: UUID,
        window: str,
        language: str = "en",
    ) -> bool:
        """
        Executa a classificação completa de intenções.

        Args:
            audience_id: ID da audiência
            analysis_id: ID da classificação já criada (status: processing)
            theme_analysis_id: ID da theme_analysis fonte dos posts
            window: Janela temporal (week ou month)
            language: Idioma preferido do usuário

        Returns:
            True se concluiu com sucesso
        """
        try:
            audience = self.audience_repo.find_by_id(audience_id)
            if not audience:
                self.intent_repo.mark_failed(analysis_id, "Audience not found")
                return False

            # 1. Buscar theme_analysis
            theme_analysis = self.theme_repo.find_latest_by_audience_and_window(
                audience_id, window
            )
            if not theme_analysis or theme_analysis.status != "ready":
                self.intent_repo.mark_failed(
                    analysis_id, "Theme analysis not found or not ready"
                )
                return False

            # 2. Carregar posts armazenados
            theme_posts = self.theme_repo.get_posts(theme_analysis.id)
            if not theme_posts:
                self.intent_repo.mark_failed(
                    analysis_id, "No posts found in theme analysis"
                )
                return False

            logger.info(
                "Loaded %d posts from theme_analysis %s for intent classification",
                len(theme_posts),
                theme_analysis.id,
            )

            # 3. Converter para formato do agente
            posts_for_agent = [
                {
                    "id": tp.post_reddit_id,
                    "subreddit": tp.subreddit,
                    "title": tp.title,
                    "selftext": tp.selftext or "",
                    "score": tp.score or 0,
                    "num_comments": tp.num_comments or 0,
                    "permalink": tp.permalink or "",
                }
                for tp in theme_posts
            ]

            communities = self.audience_repo.get_communities(audience_id)
            community_names = [c.subreddit_name for c in communities]

            period_start = (
                str(theme_analysis.period_start) if theme_analysis.period_start else ""
            )
            period_end = (
                str(theme_analysis.period_end) if theme_analysis.period_end else ""
            )

            # 4. Rodar agente de classificação
            agent = create_intent_classification_agent()
            result = agent.invoke(
                {
                    "audience_name": audience.name,
                    "audience_description": audience.description,
                    "community_names": community_names,
                    "posts": posts_for_agent,
                    "total_posts": len(posts_for_agent),
                    "time_window": window,
                    "period_start": period_start,
                    "period_end": period_end,
                    "language": language,
                    "reddit_provider": self.reddit_provider,
                    "classified_posts": [],
                    "intent_aggregations": [],
                }
            )

            classified_posts = result.get("classified_posts", [])
            intent_aggregations = result.get("intent_aggregations", [])

            if not classified_posts:
                self.intent_repo.mark_failed(analysis_id, "No posts classified")
                return False

            # 5. Salvar classificações individuais
            self.intent_repo.save_post_classifications(analysis_id, classified_posts)

            # 6. Salvar resumos por categoria
            self.intent_repo.save_intent_summaries(analysis_id, intent_aggregations)

            # 7. Marcar como pronto
            self.intent_repo.mark_ready(
                analysis_id, total_posts_classified=len(classified_posts)
            )

            # 8. Limpar análises antigas
            self.intent_repo.delete_old_analyses(audience_id, window, keep_latest=2)

            logger.info(
                "Intent classification complete for audience '%s' (%s): %d posts, %d categories",
                audience.name,
                window,
                len(classified_posts),
                len(intent_aggregations),
            )

            # 9. Notificar usuário
            try:
                from app.modules.notifications.application.services.notification_event_service import (
                    NotificationEventService,
                )

                NotificationEventService(self.db).notify_analysis_complete(
                    user_id=audience.user_id,
                    analysis_type="intent_classification",
                    analysis_id=analysis_id,
                    audience_id=audience_id,
                    audience_name=audience.name,
                )
            except Exception:
                logger.debug(
                    "Failed to send notification for intent classification complete"
                )

            return True

        except Exception as e:
            logger.exception(
                "Intent classification failed for audience %s", audience_id
            )
            try:
                self.intent_repo.mark_failed(analysis_id, str(e))
            except Exception:
                pass
            try:
                from app.modules.notifications.application.services.notification_event_service import (
                    NotificationEventService,
                )

                audience = self.audience_repo.find_by_id(audience_id)
                if audience:
                    NotificationEventService(self.db).notify_analysis_failed(
                        user_id=audience.user_id,
                        analysis_type="intent_classification",
                        analysis_id=analysis_id,
                        audience_id=audience_id,
                        audience_name=audience.name,
                        error_message=str(e),
                    )
            except Exception:
                pass
            return False
