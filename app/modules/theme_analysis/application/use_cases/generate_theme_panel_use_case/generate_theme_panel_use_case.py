"""Use case para geração de dados estruturados do painel de temas."""

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.audience_topics.infra.repositories.audience_topic_repository import (
    AudienceTopicRepository,
)
from app.modules.theme_analysis.infra.repositories.theme_analysis_repository import (
    ThemeAnalysisRepository,
)
from app.modules.theme_analysis.infra.repositories.theme_panel_repository import (
    ThemePanelRepository,
)
from app.modules.theme_analysis.infra.repositories.theme_summary_repository import (
    ThemeSummaryRepository,
)
from app.modules.theme_analysis.application.use_cases.generate_theme_panel_use_case.agent.panel_agent import (
    create_theme_panel_agent,
)

logger = logging.getLogger(__name__)

MAX_POSTS_CHARS = 30000


class GenerateThemePanelUseCase:
    """
    Gera dados estruturados do painel para um tema individual.
    Pensado para rodar em background thread.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.theme_repo = ThemeAnalysisRepository(db)
        self.topic_repo = AudienceTopicRepository(db)
        self.panel_repo = ThemePanelRepository(db)
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
        Executa a geração completa dos dados estruturados do painel.

        Returns:
            True se concluiu com sucesso
        """
        try:
            # 1. Buscar audiência
            audience = self.audience_repo.find_by_id(audience_id)
            if not audience:
                logger.error("Audience %s not found for theme panel", audience_id)
                return False

            # 2. Buscar theme_analysis e o tema específico
            theme_analysis = self.theme_repo.find_latest_by_audience_and_window(
                audience_id, window
            )
            if not theme_analysis or theme_analysis.status != "ready":
                logger.error("Theme analysis not ready for audience %s", audience_id)
                return False

            themes = self.theme_repo.get_themes(analysis_id=theme_analysis.id)
            theme = next((t for t in themes if str(t.id) == str(theme_id)), None)
            if not theme:
                logger.error(
                    "Theme %s not found in analysis %s", theme_id, theme_analysis.id
                )
                return False

            # 3. Carregar posts da análise para o prompt
            theme_posts = self.theme_repo.get_posts(theme_analysis.id)
            posts_text = self._build_posts_text(theme_posts)

            period_start = (
                str(theme_analysis.period_start) if theme_analysis.period_start else ""
            )
            period_end = (
                str(theme_analysis.period_end) if theme_analysis.period_end else ""
            )

            # 4. Invocar agente para extrair subcategorias
            agent = create_theme_panel_agent()
            result = agent.invoke(
                {
                    "audience_name": audience.name,
                    "theme_name": theme.name,
                    "time_window": window,
                    "period_start": period_start,
                    "period_end": period_end,
                    "language": language,
                    "posts_text": posts_text,
                    "subcategories": None,
                }
            )

            subcategories = result.get("subcategories") or []

            # 5. Agregar subreddits do Theme 01 (já existe no tema)
            subreddit_distribution = self._build_subreddit_distribution(theme)

            # 6. Cruzar tópicos da audiência com posts do tema
            related_topics = self._find_related_topics(audience_id, theme_posts)

            # 7. Montar action links
            action_links = {
                "view_all": f"/audiences/{audience_id}/topics?theme_filter={theme_id}",
                "patterns": f"/audiences/{audience_id}/patterns",
                "ask": f"/audiences/{audience_id}/topics/ask",
                "copy_summary": True,
            }

            # 8. Salvar painel no banco
            self.panel_repo.create_panel(
                theme_id=theme_id,
                analysis_id=analysis_id,
                fingerprint=fingerprint,
                subcategories=subcategories,
                related_topics=related_topics,
                subreddit_distribution=subreddit_distribution,
                action_links=action_links,
            )

            # 9. Limpar painéis antigos
            self.panel_repo.delete_old_panels(theme_id, keep_latest=2)

            logger.info(
                "Theme panel generated for theme '%s' (audience '%s', %s): "
                "%d subcategories, %d related topics, %d subreddits",
                theme.name,
                audience.name,
                window,
                len(subcategories),
                len(related_topics),
                len(subreddit_distribution),
            )

            # 10. Notificar usuário
            try:
                from app.modules.notifications.application.services.notification_event_service import (
                    NotificationEventService,
                )

                NotificationEventService(self.db).notify_analysis_complete(
                    user_id=audience.user_id,
                    analysis_type="theme_panel",
                    analysis_id=analysis_id,
                    audience_id=audience_id,
                    audience_name=audience.name,
                )
            except Exception:
                logger.debug("Failed to send notification for theme panel complete")

            return True

        except Exception as e:
            logger.exception("Theme panel generation failed for theme %s", theme_id)
            try:
                from app.modules.notifications.application.services.notification_event_service import (
                    NotificationEventService,
                )

                audience = self.audience_repo.find_by_id(audience_id)
                if audience:
                    NotificationEventService(self.db).notify_analysis_failed(
                        user_id=audience.user_id,
                        analysis_type="theme_panel",
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
            entry += "---\n"

            if total_chars + len(entry) > MAX_POSTS_CHARS:
                break
            lines.append(entry)
            total_chars += len(entry)

        return "".join(lines) if lines else "No posts available."

    def _build_subreddit_distribution(self, theme) -> list[dict]:
        """Agrega distribuição de subreddits do campo top_subreddits do Theme 01."""
        top_subs = theme.top_subreddits or []
        return [
            {
                "name": f"r/{sub.get('name', '')}",
                "post_count": sub.get("post_count", 0),
                "avg_score": sub.get("avg_score", 0),
            }
            for sub in top_subs
            if sub.get("name")
        ]

    def _find_related_topics(
        self,
        audience_id: UUID,
        theme_posts: list,
    ) -> list[dict]:
        """
        Cruza posts do tema com tópicos da audiência por keyword matching.
        Sem LLM — puramente programático.
        """
        try:
            # Buscar análise de tópicos mais recente (ready)
            latest_analysis = self.topic_repo.find_latest_ready(audience_id)
            if not latest_analysis:
                return []

            audience_topics = self.topic_repo.get_topics(analysis_id=latest_analysis.id)
            if not audience_topics:
                return []

            related: dict[str, dict] = {}

            for topic in audience_topics:
                keywords = self._extract_keywords(topic.name, topic.description)
                count = 0
                for post in theme_posts:
                    text = f"{post.title or ''} {post.selftext or ''}".lower()
                    if any(kw in text for kw in keywords):
                        count += 1
                if count > 0:
                    related[topic.name] = {
                        "name": topic.name,
                        "count": count,
                        "topic_id": str(topic.id),
                    }

            # Ordenar por count desc
            return sorted(related.values(), key=lambda x: x["count"], reverse=True)

        except Exception:
            logger.debug("Failed to find related topics, continuing without them")
            return []

    @staticmethod
    def _extract_keywords(name: str, description: str | None) -> list[str]:
        """Extrai keywords do nome e descrição do tópico para matching."""
        keywords = set()

        # Nome do tópico como keyword principal
        if name:
            keywords.add(name.lower().strip())
            # Palavras individuais do nome (se > 1 palavra)
            words = name.lower().strip().split()
            if len(words) > 1:
                for word in words:
                    if len(word) > 2:
                        keywords.add(word)

        # Palavras significativas da descrição
        if description:
            desc_words = description.lower().strip().split()
            stop_words = {
                "the",
                "a",
                "an",
                "is",
                "are",
                "was",
                "were",
                "be",
                "been",
                "being",
                "have",
                "has",
                "had",
                "do",
                "does",
                "did",
                "will",
                "would",
                "could",
                "should",
                "may",
                "might",
                "must",
                "shall",
                "can",
                "need",
                "dare",
                "ought",
                "used",
                "to",
                "of",
                "in",
                "for",
                "on",
                "with",
                "at",
                "by",
                "from",
                "as",
                "into",
                "through",
                "during",
                "before",
                "after",
                "above",
                "below",
                "between",
                "out",
                "off",
                "over",
                "under",
                "again",
                "further",
                "then",
                "once",
                "and",
                "but",
                "or",
                "nor",
                "not",
                "so",
                "yet",
                "both",
                "either",
                "neither",
                "each",
                "every",
                "all",
                "any",
                "few",
                "more",
                "most",
                "other",
                "some",
                "such",
                "no",
                "only",
                "own",
                "same",
                "than",
                "too",
                "very",
                "just",
                "about",
                "this",
                "that",
                "these",
                "those",
                "it",
                "its",
                "they",
                "them",
                "their",
                "what",
                "which",
                "who",
                "whom",
                "how",
                "when",
                "where",
                "why",
            }
            for word in desc_words:
                if len(word) > 3 and word not in stop_words:
                    keywords.add(word)

        return list(keywords)
