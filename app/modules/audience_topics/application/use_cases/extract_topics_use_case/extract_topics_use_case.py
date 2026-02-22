"""Use case that orchestrates topic extraction for an audience."""

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audience_topics.application.use_cases.extract_topics_use_case.agent.state import (
    PostData,
)
from app.modules.audience_topics.application.use_cases.extract_topics_use_case.agent.topic_extraction_agent import (
    create_topic_extraction_agent,
)
from app.modules.audience_topics.infra.repositories.audience_topic_repository import (
    AudienceTopicRepository,
)
from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.topics.infra.providers.reddit_provider.generic_reddit_provider import (
    GenericRedditProvider,
)

logger = logging.getLogger(__name__)


class ExtractTopicsUseCase:
    """
    Coleta posts das comunidades de uma audiência e extrai tópicos via LangGraph.
    Pensado para rodar em background thread.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.topic_repo = AudienceTopicRepository(db)
        self.reddit_provider = GenericRedditProvider()

    def execute(self, audience_id: UUID, analysis_id: UUID) -> bool:
        """
        Executa a extração completa de tópicos.

        Args:
            audience_id: ID da audiência
            analysis_id: ID da análise já criada (status: processing)

        Returns:
            True se concluiu com sucesso
        """
        try:
            audience = self.audience_repo.find_by_id(audience_id)
            if not audience:
                self.topic_repo.mark_failed(analysis_id, "Audience not found")
                return False

            communities = self.audience_repo.get_communities(audience_id)
            community_names = [c.subreddit_name for c in communities]

            if not community_names:
                self.topic_repo.mark_failed(analysis_id, "No communities in audience")
                return False

            # 1. Coletar posts das comunidades
            logger.info(
                "Collecting posts for audience '%s' (%d communities)",
                audience.name,
                len(community_names),
            )
            post_results = self.reddit_provider.collect_posts_for_communities(
                community_names, posts_per_sort=25
            )

            # 2. Converter para PostData e deduplicar
            seen_ids = set()
            posts: list[PostData] = []
            for result in post_results:
                for post in result.posts:
                    if post.id in seen_ids:
                        continue
                    seen_ids.add(post.id)
                    posts.append(
                        PostData(
                            id=post.id,
                            subreddit=post.subreddit,
                            title=post.title,
                            selftext=post.selftext,
                            score=post.score,
                            num_comments=post.num_comments,
                            created_utc=post.created_utc,
                        )
                    )

            if not posts:
                self.topic_repo.mark_failed(analysis_id, "No posts collected")
                return False

            logger.info("Collected %d unique posts, running extraction agent", len(posts))

            # 3. Rodar agente de extração
            agent = create_topic_extraction_agent()
            result = agent.invoke({
                "audience_name": audience.name,
                "audience_description": audience.description,
                "community_names": community_names,
                "posts": posts,
                "total_posts": len(posts),
                "extracted_topics": [],
            })

            extracted = result.get("extracted_topics", [])

            if not extracted:
                self.topic_repo.mark_failed(analysis_id, "No topics extracted")
                return False

            # 4. Salvar tópicos no banco
            self.topic_repo.save_topics(analysis_id, extracted)

            # 5. Marcar como pronto
            self.topic_repo.mark_ready(analysis_id, total_topics=len(extracted))

            # 6. Limpar análises antigas
            self.topic_repo.delete_old_analyses(audience_id, keep_latest=2)

            logger.info(
                "Topic extraction complete for audience '%s': %d topics",
                audience.name,
                len(extracted),
            )

            # 7. Notificar usuário
            try:
                from app.modules.notifications.application.services.notification_event_service import (
                    NotificationEventService,
                )

                NotificationEventService(self.db).notify_analysis_complete(
                    user_id=audience.user_id,
                    analysis_type="topic_analysis",
                    analysis_id=analysis_id,
                    audience_id=audience_id,
                    audience_name=audience.name,
                )
            except Exception:
                logger.debug("Failed to send notification for topic analysis complete")

            return True

        except Exception as e:
            logger.exception("Topic extraction failed for audience %s", audience_id)
            try:
                self.topic_repo.mark_failed(analysis_id, str(e))
            except Exception:
                pass
            try:
                from app.modules.notifications.application.services.notification_event_service import (
                    NotificationEventService,
                )

                NotificationEventService(self.db).notify_analysis_failed(
                    user_id=audience.user_id,
                    analysis_type="topic_analysis",
                    analysis_id=analysis_id,
                    audience_id=audience_id,
                    audience_name=audience.name,
                    error_message=str(e),
                )
            except Exception:
                pass
            return False
