"""Use case para geração de sumário narrativo enriquecido de um tema."""

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.intent_classification.infra.repositories.intent_classification_repository import (
    IntentClassificationRepository,
)
from app.modules.theme_analysis.application.use_cases.generate_theme_summary_use_case.agent.summary_agent import (
    create_theme_summary_agent,
)
from app.modules.theme_analysis.infra.repositories.theme_analysis_repository import (
    ThemeAnalysisRepository,
)
from app.modules.theme_analysis.infra.repositories.theme_summary_repository import (
    ThemeSummaryRepository,
)

logger = logging.getLogger(__name__)

MAX_POSTS_CHARS = 80_000


class GenerateThemeSummaryUseCase:
    """
    Gera sumário narrativo enriquecido para um tema individual.
    Pensado para rodar em background thread.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.theme_repo = ThemeAnalysisRepository(db)
        self.intent_repo = IntentClassificationRepository(db)
        self.summary_repo = ThemeSummaryRepository(db)

    def execute(
        self,
        audience_id: UUID,
        theme_id: UUID,
        analysis_id: UUID,
        window: str,
        fingerprint: str,
        language: str = "en",
    ) -> bool:
        """
        Executa a geração completa do sumário narrativo.

        Args:
            audience_id: ID da audiência
            theme_id: ID do tema para gerar o sumário
            analysis_id: ID da theme_analysis fonte
            window: Janela temporal (week ou month)
            fingerprint: Fingerprint para o sumário
            language: Idioma preferido do usuário

        Returns:
            True se concluiu com sucesso
        """
        try:
            # 1. Buscar audiência
            audience = self.audience_repo.find_by_id(audience_id)
            if not audience:
                logger.error("Audience %s not found for theme summary", audience_id)
                return False

            # 2. Buscar theme_analysis e o tema específico
            theme_analysis = self.theme_repo.find_latest_by_audience_and_window(
                audience_id, window
            )
            if not theme_analysis or theme_analysis.status != "ready":
                logger.error("Theme analysis not ready for audience %s", audience_id)
                return False

            # Buscar o tema específico
            themes = self.theme_repo.get_themes(analysis_id=theme_analysis.id)
            theme = next((t for t in themes if str(t.id) == str(theme_id)), None)
            if not theme:
                logger.error("Theme %s not found in analysis %s", theme_id, theme_analysis.id)
                return False

            # 3. Carregar posts da análise para formatar no prompt
            theme_posts = self.theme_repo.get_posts(theme_analysis.id)
            posts_text = self._build_posts_text(theme_posts)

            # 4. Buscar dados de comunidades
            communities = self.audience_repo.get_communities(audience_id)
            community_names = [c.subreddit_name for c in communities]

            period_start = (
                str(theme_analysis.period_start) if theme_analysis.period_start else ""
            )
            period_end = (
                str(theme_analysis.period_end) if theme_analysis.period_end else ""
            )

            # 5. Opcionalmente buscar dados de intenção (Theme 02)
            intent_breakdown = self._get_intent_breakdown(audience_id, window)

            # 6. Buscar temas anteriores para diferenciador temporal
            previous_themes = self._get_previous_themes(audience_id, window, theme_analysis.id)

            # 7. Preparar dados do tema
            theme_data = {
                "theme_id": str(theme.id),
                "theme_name": theme.name,
                "summary": theme.summary,
                "post_count": theme.post_count or 0,
                "avg_score": theme.avg_score or 0,
                "avg_comments": theme.avg_comments or 0,
                "top_subreddits": theme.top_subreddits or [],
                "top_keywords": theme.top_keywords or [],
                "representative_posts": theme.representative_posts or [],
            }

            # 8. Invocar agente
            agent = create_theme_summary_agent()
            result = agent.invoke(
                {
                    "audience_name": audience.name,
                    "audience_description": audience.description,
                    "community_names": community_names,
                    "time_window": window,
                    "period_start": period_start,
                    "period_end": period_end,
                    "language": language,
                    "theme_data": theme_data,
                    "posts_text": posts_text,
                    "intent_breakdown": intent_breakdown,
                    "previous_themes": previous_themes,
                    "summary_result": None,
                }
            )

            summary_result = result.get("summary_result")
            if not summary_result:
                logger.error("No summary result from agent for theme %s", theme_id)
                return False

            # 9. Salvar sumário
            self.summary_repo.create_summary(
                theme_id=theme_id,
                analysis_id=analysis_id,
                fingerprint=fingerprint,
                narrative=summary_result["narrative"],
                highlights=summary_result["highlights"],
                emotional_tone=summary_result["emotional_tone"],
                tone_description=summary_result["tone_description"],
                key_themes=summary_result["key_themes"],
                intent_breakdown=intent_breakdown,
                week_differentiator=summary_result.get("week_differentiator"),
            )

            # 10. Limpar sumários antigos
            self.summary_repo.delete_old_summaries(theme_id, keep_latest=2)

            logger.info(
                "Theme summary generated for theme '%s' (audience '%s', %s)",
                theme.name,
                audience.name,
                window,
            )

            # 11. Notificar usuário
            try:
                from app.modules.notifications.application.services.notification_event_service import (
                    NotificationEventService,
                )

                NotificationEventService(self.db).notify_analysis_complete(
                    user_id=audience.user_id,
                    analysis_type="theme_summary",
                    analysis_id=analysis_id,
                    audience_id=audience_id,
                    audience_name=audience.name,
                )
            except Exception:
                logger.debug("Failed to send notification for theme summary complete")

            return True

        except Exception as e:
            logger.exception(
                "Theme summary generation failed for theme %s", theme_id
            )
            try:
                from app.modules.notifications.application.services.notification_event_service import (
                    NotificationEventService,
                )

                audience = self.audience_repo.find_by_id(audience_id)
                if audience:
                    NotificationEventService(self.db).notify_analysis_failed(
                        user_id=audience.user_id,
                        analysis_type="theme_summary",
                        analysis_id=analysis_id,
                        audience_id=audience_id,
                        audience_name=audience.name,
                        error_message=str(e),
                    )
            except Exception:
                pass
            return False

    def _build_posts_text(self, theme_posts: list) -> str:
        """Formata posts para injeção no prompt do agente."""
        lines: list[str] = []
        total_chars = 0

        for post in theme_posts:
            selftext = (post.selftext or "")[:300]
            entry = (
                f"[r/{post.subreddit}] (score: {post.score or 0}, "
                f"comments: {post.num_comments or 0})\n"
                f"Title: {post.title}\n"
            )
            if selftext.strip():
                entry += f"Body: {selftext}\n"
            if post.permalink:
                entry += f"permalink: {post.permalink}\n"
            entry += "---\n"

            if total_chars + len(entry) > MAX_POSTS_CHARS:
                break
            lines.append(entry)
            total_chars += len(entry)

        return "".join(lines) if lines else "No posts available."

    def _get_intent_breakdown(
        self, audience_id: UUID, window: str
    ) -> dict | None:
        """Busca dados de intenção do Theme 02 se disponíveis."""
        try:
            latest_intent = self.intent_repo.find_latest_by_audience_and_window(
                audience_id, window
            )
            if not latest_intent or latest_intent.status != "ready":
                return None

            summaries = self.intent_repo.get_intent_summaries(latest_intent.id)
            if not summaries:
                return None

            return {s.intent_category: s.post_count for s in summaries}

        except Exception:
            logger.debug("Failed to fetch intent breakdown, continuing without it")
            return None

    def _get_previous_themes(
        self, audience_id: UUID, window: str, current_analysis_id: UUID
    ) -> list[str] | None:
        """Busca nomes de temas da análise anterior para diferenciador temporal."""
        try:
            from app.modules.theme_analysis.domain.entities.theme import ThemeAnalysis

            # Buscar a análise anterior (não a atual)
            previous = (
                self.db.query(ThemeAnalysis)
                .filter(
                    ThemeAnalysis.audience_id == audience_id,
                    ThemeAnalysis.time_window == window,
                    ThemeAnalysis.status == "ready",
                    ThemeAnalysis.id != current_analysis_id,
                )
                .order_by(ThemeAnalysis.created_at.desc())
                .first()
            )
            if not previous:
                return None

            previous_themes = self.theme_repo.get_themes(analysis_id=previous.id)
            if not previous_themes:
                return None

            return [t.name for t in previous_themes]

        except Exception:
            logger.debug("Failed to fetch previous themes, continuing without them")
            return None
