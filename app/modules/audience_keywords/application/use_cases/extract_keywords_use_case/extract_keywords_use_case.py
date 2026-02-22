"""Use case that orchestrates keyword extraction for an audience."""

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audience_keywords.application.use_cases.extract_keywords_use_case.agent.keyword_extraction_agent import (
    create_keyword_extraction_agent,
)
from app.modules.audience_keywords.infra.repositories.audience_keyword_repository import (
    AudienceKeywordRepository,
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


class ExtractKeywordsUseCase:
    """
    Coleta contexto das comunidades de uma audiência e extrai keywords via LangGraph.
    Pensado para rodar em background thread.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.keyword_repo = AudienceKeywordRepository(db)
        self.topic_repo = AudienceTopicRepository(db)
        self.reddit_provider = GenericRedditProvider()

    def execute(self, audience_id: UUID, analysis_id: UUID, language: str = "en") -> bool:
        """
        Executa a extração completa de keywords.

        Args:
            audience_id: ID da audiência
            analysis_id: ID da análise já criada (status: processing)
            language: Idioma preferido do usuário

        Returns:
            True se concluiu com sucesso
        """
        try:
            audience = self.audience_repo.find_by_id(audience_id)
            if not audience:
                self.keyword_repo.mark_failed(analysis_id, "Audience not found")
                return False

            communities = self.audience_repo.get_communities(audience_id)
            community_names = [c.subreddit_name for c in communities]

            if not community_names:
                self.keyword_repo.mark_failed(analysis_id, "No communities in audience")
                return False

            # 1. Coletar descrições das comunidades
            logger.info(
                "Collecting community descriptions for audience '%s' (%d communities)",
                audience.name,
                len(community_names),
            )
            community_descriptions = self._collect_community_descriptions(community_names)

            # 2. Buscar tópicos já extraídos (se existirem)
            topics_summary = self._get_topics_summary(audience_id)

            # 3. Rodar agente de extração de keywords
            logger.info("Running keyword extraction agent for audience '%s'", audience.name)
            agent = create_keyword_extraction_agent()
            result = agent.invoke({
                "audience_name": audience.name,
                "audience_description": audience.description,
                "community_names": community_names,
                "community_descriptions": community_descriptions,
                "topics_summary": topics_summary,
                "language": language,
                "extracted_keywords": [],
            })

            extracted = result.get("extracted_keywords", [])

            if not extracted:
                self.keyword_repo.mark_failed(analysis_id, "No keywords extracted")
                return False

            # 4. Salvar keywords no banco
            self.keyword_repo.save_keywords(analysis_id, extracted)

            # 5. Marcar como pronto
            self.keyword_repo.mark_ready(analysis_id, total_keywords=len(extracted))

            # 6. Limpar análises antigas
            self.keyword_repo.delete_old_analyses(audience_id, keep_latest=2)

            logger.info(
                "Keyword extraction complete for audience '%s': %d keywords",
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
                    analysis_type="keyword_analysis",
                    analysis_id=analysis_id,
                    audience_id=audience_id,
                    audience_name=audience.name,
                )
            except Exception:
                logger.debug("Failed to send notification for keyword analysis complete")

            return True

        except Exception as e:
            logger.exception("Keyword extraction failed for audience %s", audience_id)
            try:
                self.keyword_repo.mark_failed(analysis_id, str(e))
            except Exception:
                pass
            try:
                from app.modules.notifications.application.services.notification_event_service import (
                    NotificationEventService,
                )

                NotificationEventService(self.db).notify_analysis_failed(
                    user_id=audience.user_id,
                    analysis_type="keyword_analysis",
                    analysis_id=analysis_id,
                    audience_id=audience_id,
                    audience_name=audience.name,
                    error_message=str(e),
                )
            except Exception:
                pass
            return False

    def _collect_community_descriptions(self, community_names: list[str]) -> list[str]:
        """Busca descrições das comunidades via Reddit API."""
        descriptions = []
        for name in community_names:
            try:
                response = self.reddit_provider.get_community_details(name)
                data = response.get("data", response)
                desc = data.get("public_description") or data.get("description") or ""
                # Truncate long descriptions
                if len(desc) > 300:
                    desc = desc[:300] + "..."
                descriptions.append(desc)
            except Exception:
                descriptions.append("")
        return descriptions

    def _get_topics_summary(self, audience_id: UUID) -> str | None:
        """Busca resumo dos tópicos já extraídos para enriquecer a geração de keywords."""
        latest_analysis = self.topic_repo.find_latest_ready(audience_id)
        if not latest_analysis:
            return None

        topics = self.topic_repo.get_topics(
            analysis_id=latest_analysis.id,
            sort_by="rank",
            limit=20,
        )

        if not topics:
            return None

        lines = []
        for t in topics:
            growth = f" (growth: {t.growth_percentage}%)" if t.growth_percentage else ""
            lines.append(f"- {t.name}: {t.description}{growth}")

        return "\n".join(lines)
