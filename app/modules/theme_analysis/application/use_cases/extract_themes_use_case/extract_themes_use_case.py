"""Use case para extração de temas temporais (roda em background thread)."""

import logging
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.theme_analysis.application.use_cases.extract_themes_use_case.agent.state import (
    PostData,
)
from app.modules.theme_analysis.application.use_cases.extract_themes_use_case.agent.theme_extraction_agent import (
    create_theme_extraction_agent,
)
from app.modules.theme_analysis.infra.repositories.theme_analysis_repository import (
    ThemeAnalysisRepository,
)
from app.modules.topics.infra.providers.reddit_provider.generic_reddit_provider import (
    GenericRedditProvider,
)

logger = logging.getLogger(__name__)


def _filter_posts_by_window(posts: list[dict], window: str) -> list[dict]:
    """Filtra posts por janela temporal baseado em created_utc."""
    now = datetime.utcnow()
    if window == "week":
        cutoff = now - timedelta(days=7)
    elif window == "month":
        cutoff = now - timedelta(days=30)
    else:
        return posts

    cutoff_ts = cutoff.timestamp()
    return [p for p in posts if (p.get("created_utc") or 0) >= cutoff_ts]


class ExtractThemesUseCase:
    """
    Coleta posts filtrados por janela temporal e extrai temas via LangGraph.
    Pensado para rodar em background thread.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.theme_repo = ThemeAnalysisRepository(db)
        self.reddit_provider = GenericRedditProvider()

    def _collect_posts_for_window(
        self, community_names: list[str], window: str
    ) -> list[PostData]:
        """Coleta posts do Reddit com sorts adequados para a janela temporal."""
        all_raw_posts = []

        for community in community_names:
            if window == "week":
                # Hot + new para capturar o que está quente e o que acabou de surgir
                for sort in ("hot", "new"):
                    result = self.reddit_provider.get_subreddit_posts(
                        subreddit_name=community,
                        sort=sort,
                        limit=50,
                    )
                    for post in result.posts:
                        all_raw_posts.append(
                            {
                                "id": post.id,
                                "subreddit": post.subreddit,
                                "title": post.title,
                                "selftext": post.selftext,
                                "score": post.score,
                                "num_comments": post.num_comments,
                                "created_utc": post.created_utc,
                                "permalink": post.permalink or "",
                            }
                        )
            elif window == "month":
                # Top do mês para capturar melhor conteúdo
                result = self.reddit_provider.get_subreddit_posts(
                    subreddit_name=community,
                    sort="top",
                    limit=50,
                    time_filter="month",
                )
                for post in result.posts:
                    all_raw_posts.append(
                        {
                            "id": post.id,
                            "subreddit": post.subreddit,
                            "title": post.title,
                            "selftext": post.selftext,
                            "score": post.score,
                            "num_comments": post.num_comments,
                            "created_utc": post.created_utc,
                            "permalink": post.permalink or "",
                        }
                    )

        # Filtrar por janela temporal
        filtered = _filter_posts_by_window(all_raw_posts, window)

        # Deduplicar por post ID
        seen_ids: set[str] = set()
        unique_posts: list[PostData] = []
        for post in filtered:
            if post["id"] in seen_ids:
                continue
            seen_ids.add(post["id"])
            unique_posts.append(
                PostData(
                    id=post["id"],
                    subreddit=post["subreddit"],
                    title=post["title"],
                    selftext=post["selftext"],
                    score=post["score"],
                    num_comments=post["num_comments"],
                    created_utc=post["created_utc"],
                    permalink=post.get("permalink", ""),
                )
            )

        return unique_posts

    def execute(
        self,
        audience_id: UUID,
        analysis_id: UUID,
        window: str,
        language: str = "en",
    ) -> bool:
        """
        Executa a extração completa de temas temporais.

        Args:
            audience_id: ID da audiência
            analysis_id: ID da análise já criada (status: processing)
            window: Janela temporal (week ou month)
            language: Idioma preferido do usuário

        Returns:
            True se concluiu com sucesso
        """
        try:
            audience = self.audience_repo.find_by_id(audience_id)
            if not audience:
                self.theme_repo.mark_failed(analysis_id, "Audience not found")
                return False

            communities = self.audience_repo.get_communities(audience_id)
            community_names = [c.subreddit_name for c in communities]

            if not community_names:
                self.theme_repo.mark_failed(analysis_id, "No communities in audience")
                return False

            # 1. Coletar posts filtrados por janela temporal
            logger.info(
                "Collecting %s posts for audience '%s' (%d communities)",
                window,
                audience.name,
                len(community_names),
            )
            posts = self._collect_posts_for_window(community_names, window)

            if not posts:
                self.theme_repo.mark_failed(
                    analysis_id,
                    f"No posts found for {window} window",
                )
                return False

            logger.info(
                "Collected %d unique posts for %s window, running theme extraction agent",
                len(posts),
                window,
            )

            # 1.5 Salvar posts coletados para reutilização por outros módulos
            self.theme_repo.save_posts(analysis_id, posts)
            logger.info("Saved %d posts for analysis %s", len(posts), analysis_id)

            # 2. Calcular período
            period_start, period_end = ThemeAnalysisRepository.get_period_bounds(window)

            # 3. Rodar agente de extração
            agent = create_theme_extraction_agent()
            result = agent.invoke(
                {
                    "audience_name": audience.name,
                    "audience_description": audience.description,
                    "community_names": community_names,
                    "posts": posts,
                    "total_posts": len(posts),
                    "time_window": window,
                    "period_start": str(period_start),
                    "period_end": str(period_end),
                    "language": language,
                    "extracted_themes": [],
                }
            )

            extracted = result.get("extracted_themes", [])

            if not extracted:
                self.theme_repo.mark_failed(analysis_id, "No themes extracted")
                return False

            # 4. Salvar temas no banco
            self.theme_repo.save_themes(analysis_id, extracted)

            # 5. Marcar como pronto
            self.theme_repo.mark_ready(analysis_id, total_themes=len(extracted))

            # 6. Limpar análises antigas
            self.theme_repo.delete_old_analyses(audience_id, window, keep_latest=2)

            logger.info(
                "Theme extraction complete for audience '%s' (%s): %d themes",
                audience.name,
                window,
                len(extracted),
            )

            # 7. Avaliar alertas inteligentes
            try:
                from app.modules.topic_alerts.application.use_cases.evaluate_alerts_use_case import (
                    EvaluateAlertsUseCase,
                )

                EvaluateAlertsUseCase(self.db).evaluate_themes(
                    audience_id=audience_id,
                    analysis_id=analysis_id,
                    user_id=audience.user_id,
                    audience_name=audience.name,
                    time_window=window,
                )
            except Exception:
                logger.debug("Failed to evaluate theme alerts")

            # 8. Notificar usuário
            try:
                from app.modules.notifications.application.services.notification_event_service import (
                    NotificationEventService,
                )

                NotificationEventService(self.db).notify_analysis_complete(
                    user_id=audience.user_id,
                    analysis_type="theme_analysis",
                    analysis_id=analysis_id,
                    audience_id=audience_id,
                    audience_name=audience.name,
                )
            except Exception:
                logger.debug("Failed to send notification for theme analysis complete")

            return True

        except Exception as e:
            logger.exception("Theme extraction failed for audience %s", audience_id)
            try:
                self.theme_repo.mark_failed(analysis_id, str(e))
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
                        analysis_type="theme_analysis",
                        analysis_id=analysis_id,
                        audience_id=audience_id,
                        audience_name=audience.name,
                        error_message=str(e),
                    )
            except Exception:
                pass
            return False
