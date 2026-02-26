"""Use case that orchestrates deep dive analysis for a topic."""

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.topic_deep_dive.application.use_cases.extract_deep_dive_use_case.agent.deep_dive_agent import (
    create_deep_dive_agent,
    _get_limits as _get_deep_dive_limits,
)
from app.modules.topic_deep_dive.application.use_cases.extract_deep_dive_use_case.agent.state import (
    PostWithComments,
)
from app.modules.topic_deep_dive.infra.repositories.topic_deep_dive_repository import (
    TopicDeepDiveRepository,
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


class ExtractDeepDiveUseCase:
    """
    Coleta posts + comentários relacionados a um tópico e roda deep dive via LangGraph.
    Pensado para rodar em background thread.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.topic_repo = AudienceTopicRepository(db)
        self.deep_dive_repo = TopicDeepDiveRepository(db)
        self.reddit_provider = GenericRedditProvider()

    def execute(self, topic_id: UUID, audience_id: UUID, analysis_id: UUID, language: str = "en") -> bool:
        """
        Executa a análise de deep dive completa.

        Args:
            topic_id: ID do tópico
            audience_id: ID da audiência
            analysis_id: ID da análise já criada (status: processing)
            language: Idioma preferido do usuário

        Returns:
            True se concluiu com sucesso
        """
        try:
            # 1. Buscar dados do tópico e audiência
            audience = self.audience_repo.find_by_id(audience_id)
            if not audience:
                self.deep_dive_repo.mark_failed(analysis_id, "Audience not found")
                return False

            topic = self.topic_repo.get_topic_by_id(topic_id)
            if not topic:
                self.deep_dive_repo.mark_failed(analysis_id, "Topic not found")
                return False

            communities = self.audience_repo.get_communities(audience_id)
            community_names = [c.subreddit_name for c in communities]

            if not community_names:
                self.deep_dive_repo.mark_failed(analysis_id, "No communities in audience")
                return False

            # 2. Coletar posts das comunidades do tópico
            topic_communities = topic.communities or []
            topic_community_names = [
                c["name"].removeprefix("r/") for c in topic_communities if c.get("name")
            ]

            # Se o tópico não tem comunidades específicas, usar todas da audiência
            if not topic_community_names:
                topic_community_names = community_names

            logger.info(
                "Collecting posts for deep dive on topic '%s' from %d communities",
                topic.name,
                len(topic_community_names),
            )

            post_results = self.reddit_provider.collect_posts_for_communities(
                topic_community_names, posts_per_sort=25
            )

            # 3. Filtrar posts relevantes ao tópico e deduplicar
            seen_ids = set()
            all_posts = []
            for result in post_results:
                for post in result.posts:
                    if post.id in seen_ids:
                        continue
                    seen_ids.add(post.id)
                    all_posts.append(post)

            # Filtrar por relevância ao tópico (título ou texto contém keywords do tópico)
            topic_keywords = self._extract_topic_keywords(topic.name, topic.description)
            relevant_posts = self._filter_relevant_posts(all_posts, topic_keywords)

            if not relevant_posts:
                # Se nenhum post é diretamente relevante, usar todos (o LLM filtra)
                relevant_posts = all_posts

            # Ordenar por score (mais engajados primeiro)
            relevant_posts.sort(key=lambda p: p.score, reverse=True)

            logger.info(
                "Found %d relevant posts out of %d total for topic '%s'",
                len(relevant_posts),
                len(all_posts),
                topic.name,
            )

            # 4. Buscar comentários dos top posts
            limits = _get_deep_dive_limits()
            posts_with_comments: list[PostWithComments] = []
            for i, post in enumerate(relevant_posts):
                comments = []
                if i < limits.top_posts_for_comments:
                    raw_comments = self.reddit_provider.get_post_comments(
                        post.subreddit, post.id, limit=limits.comments_per_post_fetch
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

            if not posts_with_comments:
                self.deep_dive_repo.mark_failed(analysis_id, "No posts collected")
                return False

            total_comments = sum(len(p["comments"]) for p in posts_with_comments)
            logger.info(
                "Collected %d posts with %d comments, running deep dive agent",
                len(posts_with_comments),
                total_comments,
            )

            # 5. Rodar agente de deep dive
            agent = create_deep_dive_agent()
            result = agent.invoke({
                "topic_name": topic.name,
                "topic_description": topic.description or "",
                "audience_name": audience.name,
                "community_names": community_names,
                "language": language,
                "relevant_posts": posts_with_comments,
                "deep_dive_result": None,
            })

            deep_dive_result = result.get("deep_dive_result")

            if not deep_dive_result:
                self.deep_dive_repo.mark_failed(analysis_id, "Deep dive analysis returned no results")
                return False

            # 6. Salvar resultado no banco
            self.deep_dive_repo.save_deep_dive(analysis_id, deep_dive_result)

            # 7. Marcar como pronto
            self.deep_dive_repo.mark_ready(analysis_id)

            # 8. Limpar análises antigas
            self.deep_dive_repo.delete_old_analyses(topic_id, keep_latest=2)

            logger.info(
                "Deep dive complete for topic '%s': %d subtopics, %d insights",
                topic.name,
                len(deep_dive_result.get("subtopics", [])),
                len(deep_dive_result.get("actionable_insights", [])),
            )

            # 9. Notificar usuário
            try:
                from app.modules.notifications.application.services.notification_event_service import (
                    NotificationEventService,
                )

                NotificationEventService(self.db).notify_analysis_complete(
                    user_id=audience.user_id,
                    analysis_type="deep_dive",
                    analysis_id=analysis_id,
                    audience_id=audience_id,
                    audience_name=audience.name,
                    topic_id=topic_id,
                    topic_name=topic.name,
                )
            except Exception:
                logger.debug("Failed to send notification for deep dive complete")

            return True

        except Exception as e:
            logger.exception("Deep dive failed for topic %s", topic_id)
            try:
                self.deep_dive_repo.mark_failed(analysis_id, str(e))
            except Exception:
                pass
            try:
                from app.modules.notifications.application.services.notification_event_service import (
                    NotificationEventService,
                )

                NotificationEventService(self.db).notify_analysis_failed(
                    user_id=audience.user_id,
                    analysis_type="deep_dive",
                    analysis_id=analysis_id,
                    audience_id=audience_id,
                    audience_name=audience.name,
                    error_message=str(e),
                    topic_id=topic_id,
                    topic_name=topic.name if topic else None,
                )
            except Exception:
                pass
            return False

    def _extract_topic_keywords(self, name: str, description: str | None) -> list[str]:
        """Extrai keywords do nome e descrição do tópico para filtragem."""
        text = name.lower()
        if description:
            text += " " + description.lower()

        # Remove palavras muito genéricas
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "can", "shall",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "and",
            "but", "or", "nor", "not", "so", "yet", "both", "either",
            "neither", "each", "every", "all", "any", "few", "more",
            "most", "other", "some", "such", "no", "only", "own", "same",
            "than", "too", "very", "just", "about", "this", "that",
            "these", "those", "it", "its", "they", "them", "their",
            "related", "discussions", "topics", "issues", "content",
        }

        words = text.split()
        keywords = [w.strip(".,!?;:'\"()[]{}") for w in words if len(w) > 2]
        keywords = [w for w in keywords if w and w not in stop_words]

        return list(set(keywords))

    def _filter_relevant_posts(self, posts: list, keywords: list[str]) -> list:
        """Filtra posts que contêm keywords do tópico."""
        if not keywords:
            return posts

        relevant = []
        for post in posts:
            text = (post.title + " " + post.selftext).lower()
            if any(kw in text for kw in keywords):
                relevant.append(post)

        return relevant
