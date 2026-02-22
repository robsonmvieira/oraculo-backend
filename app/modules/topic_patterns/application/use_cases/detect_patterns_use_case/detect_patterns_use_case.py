"""Use case that orchestrates cross-topic pattern detection for an audience."""

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.topic_patterns.application.use_cases.detect_patterns_use_case.agent.pattern_detection_agent import (
    create_pattern_detection_agent,
)
from app.modules.topic_patterns.application.use_cases.detect_patterns_use_case.agent.state import (
    PostWithComments,
    TopicSummary,
)
from app.modules.topic_patterns.infra.repositories.topic_pattern_repository import (
    TopicPatternRepository,
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

TOP_POSTS_FOR_COMMENTS = 10
COMMENTS_PER_POST = 20


class DetectPatternsUseCase:
    """
    Coleta todos os topicos + posts + comentarios de uma audiencia
    e roda deteccao de padroes cross-topic via LangGraph.
    Pensado para rodar em background thread.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.topic_repo = AudienceTopicRepository(db)
        self.pattern_repo = TopicPatternRepository(db)
        self.reddit_provider = GenericRedditProvider()

    def execute(self, audience_id: UUID, analysis_id: UUID) -> bool:
        """
        Executa a deteccao de padroes completa.

        Args:
            audience_id: ID da audiencia
            analysis_id: ID da analise ja criada (status: processing)

        Returns:
            True se concluiu com sucesso
        """
        try:
            # 1. Buscar audiencia e comunidades
            audience = self.audience_repo.find_by_id(audience_id)
            if not audience:
                self.pattern_repo.mark_failed(analysis_id, "Audience not found")
                return False

            communities = self.audience_repo.get_communities(audience_id)
            community_names = [c.subreddit_name for c in communities]

            if not community_names:
                self.pattern_repo.mark_failed(analysis_id, "No communities in audience")
                return False

            # 2. Buscar todos os topicos da audiencia (analise mais recente com status ready)
            latest_analysis = self.topic_repo.find_latest_by_audience(audience_id)
            if not latest_analysis or latest_analysis.status != "ready":
                self.pattern_repo.mark_failed(
                    analysis_id, "No ready topic analysis found for audience"
                )
                return False

            topics_raw = self.topic_repo.get_topics(
                analysis_id=latest_analysis.id, limit=200
            )
            if not topics_raw:
                self.pattern_repo.mark_failed(analysis_id, "No topics found for audience")
                return False

            topics: list[TopicSummary] = []
            for t in topics_raw:
                topic_communities = t.communities or []
                topics.append(
                    TopicSummary(
                        name=t.name,
                        description=t.description or "",
                        communities=[c.get("name", "") for c in topic_communities],
                        estimated_frequency=str(t.mention_frequency or "unknown"),
                        growth_trend=str(t.growth_percentage or "unknown"),
                    )
                )

            logger.info(
                "Collecting posts for pattern detection on audience '%s' (%d topics, %d communities)",
                audience.name,
                len(topics),
                len(community_names),
            )

            # 3. Coletar posts de todas as comunidades da audiencia
            post_results = self.reddit_provider.collect_posts_for_communities(
                community_names, posts_per_sort=25
            )

            # Deduplicar posts
            seen_ids = set()
            all_posts = []
            for result in post_results:
                for post in result.posts:
                    if post.id in seen_ids:
                        continue
                    seen_ids.add(post.id)
                    all_posts.append(post)

            # Ordenar por score (mais engajados primeiro)
            all_posts.sort(key=lambda p: p.score, reverse=True)

            logger.info(
                "Found %d unique posts from %d communities",
                len(all_posts),
                len(community_names),
            )

            if not all_posts:
                self.pattern_repo.mark_failed(analysis_id, "No posts collected")
                return False

            # 4. Buscar comentarios dos top posts
            posts_with_comments: list[PostWithComments] = []
            for i, post in enumerate(all_posts):
                comments = []
                if i < TOP_POSTS_FOR_COMMENTS:
                    raw_comments = self.reddit_provider.get_post_comments(
                        post.subreddit, post.id, limit=COMMENTS_PER_POST
                    )
                    comments = [
                        {
                            "body": c.body,
                            "score": c.score,
                            "author": c.author,
                        }
                        for c in raw_comments
                    ]

                posts_with_comments.append(
                    PostWithComments(
                        id=post.id,
                        subreddit=post.subreddit,
                        title=post.title,
                        selftext=post.selftext,
                        score=post.score,
                        num_comments=post.num_comments,
                        created_utc=post.created_utc,
                        permalink=post.permalink,
                        comments=comments,
                    )
                )

            total_comments = sum(len(p["comments"]) for p in posts_with_comments)
            logger.info(
                "Collected %d posts with %d comments, running pattern detection agent",
                len(posts_with_comments),
                total_comments,
            )

            # 5. Rodar agente de deteccao de padroes
            agent = create_pattern_detection_agent()
            result = agent.invoke({
                "audience_name": audience.name,
                "community_names": community_names,
                "topics": topics,
                "posts_with_comments": posts_with_comments,
                "pattern_result": None,
            })

            pattern_result = result.get("pattern_result")

            if not pattern_result:
                self.pattern_repo.mark_failed(
                    analysis_id, "Pattern detection returned no results"
                )
                return False

            # 6. Salvar resultado no banco
            self.pattern_repo.save_pattern(analysis_id, pattern_result)

            # 7. Marcar como pronto
            self.pattern_repo.mark_ready(analysis_id)

            # 8. Limpar analises antigas
            self.pattern_repo.delete_old_analyses(audience_id, keep_latest=2)

            logger.info(
                "Pattern detection complete for audience '%s': %d co-occurrences, %d opportunities",
                audience.name,
                len(pattern_result.get("co_occurrences", [])),
                len(pattern_result.get("content_opportunities", [])),
            )

            # 9. Notificar usuário
            try:
                from app.modules.notifications.application.services.notification_event_service import (
                    NotificationEventService,
                )

                NotificationEventService(self.db).notify_analysis_complete(
                    user_id=audience.user_id,
                    analysis_type="pattern_analysis",
                    analysis_id=analysis_id,
                    audience_id=audience_id,
                    audience_name=audience.name,
                )
            except Exception:
                logger.debug("Failed to send notification for pattern analysis complete")

            return True

        except Exception as e:
            logger.exception("Pattern detection failed for audience %s", audience_id)
            try:
                self.pattern_repo.mark_failed(analysis_id, str(e))
            except Exception:
                pass
            try:
                from app.modules.notifications.application.services.notification_event_service import (
                    NotificationEventService,
                )

                NotificationEventService(self.db).notify_analysis_failed(
                    user_id=audience.user_id,
                    analysis_type="pattern_analysis",
                    analysis_id=analysis_id,
                    audience_id=audience_id,
                    audience_name=audience.name,
                    error_message=str(e),
                )
            except Exception:
                pass
            return False
