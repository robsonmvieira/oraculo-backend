"""Use case para geração de sugestões inteligentes de conteúdo."""

import logging
import os
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.content_suggestions.application.use_cases.generate_suggestions_use_case.agent.content_suggestion_agent import (
    create_content_suggestion_agent,
)
from app.modules.content_suggestions.application.use_cases.generate_suggestions_use_case.context_builder import (
    ContextBuilder,
)
from app.modules.content_suggestions.infra.repositories.content_suggestion_repository import (
    ContentSuggestionRepository,
)

logger = logging.getLogger(__name__)


class GenerateSuggestionsUseCase:
    """
    Coleta dados de todos os módulos analíticos, invoca agente LangGraph e salva sugestões.
    Pensado para rodar em background thread.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.suggestion_repo = ContentSuggestionRepository(db)

    def execute(
        self,
        audience_id: UUID,
        analysis_id: UUID,
        language: str = "en",
    ) -> bool:
        """
        Executa a geração completa de sugestões.

        Args:
            audience_id: ID da audiência
            analysis_id: ID da análise já criada (status: processing)
            language: Idioma preferido do usuário

        Returns:
            True se concluiu com sucesso
        """
        try:
            # 1. Buscar audiência
            audience = self.audience_repo.find_by_id(audience_id)
            if not audience:
                self.suggestion_repo.mark_failed(analysis_id, "Audience not found")
                return False

            communities = self.audience_repo.get_communities(audience_id)
            community_names = [c.subreddit_name for c in communities]

            if not community_names:
                self.suggestion_repo.mark_failed(
                    analysis_id, "No communities in audience"
                )
                return False

            # 2. Montar contexto de todos os módulos
            builder = ContextBuilder(self.db)
            assembled_context, modules_available, topic_contexts, _ = builder.build(
                audience_id
            )

            if not topic_contexts:
                self.suggestion_repo.mark_failed(
                    analysis_id, "No topic analysis available"
                )
                return False

            logger.info(
                "Running content suggestion agent for audience '%s' with %d modules",
                audience.name,
                len(modules_available),
            )

            # 3. Rodar agente LangGraph
            agent = create_content_suggestion_agent()
            model_name = os.getenv(
                "CONTENT_SUGGESTION_MODEL",
                os.getenv("MODEL_NAME", "gpt-5-nano-2025-08-07"),
            )

            result = agent.invoke(
                {
                    "audience_id": str(audience_id),
                    "audience_name": audience.name,
                    "audience_description": audience.description,
                    "community_names": community_names,
                    "language": language,
                    "assembled_context": assembled_context,
                    "modules_available": modules_available,
                    "topic_contexts": topic_contexts,
                    "ranked_opportunities": [],
                    "content_suggestions": [],
                    "differentiated_suggestions": [],
                    "verified_suggestions": [],
                }
            )

            verified = result.get("verified_suggestions", [])

            if not verified:
                self.suggestion_repo.mark_failed(
                    analysis_id, "Agent returned no suggestions"
                )
                return False

            # 4. Salvar sugestões
            self.suggestion_repo.save_suggestions(analysis_id, verified)

            # 5. Marcar como pronto
            self.suggestion_repo.mark_ready(
                analysis_id,
                modules_used=modules_available,
                model_used=model_name,
            )

            # 6. Limpar análises antigas
            self.suggestion_repo.delete_old_analyses(audience_id, keep_latest=3)

            logger.info(
                "Content suggestions complete for audience '%s': %d suggestions",
                audience.name,
                len(verified),
            )

            # 7. Notificar usuário
            try:
                from app.modules.notifications.application.services.notification_event_service import (
                    NotificationEventService,
                )

                top_title = verified[0].get("title", "N/A") if verified else "N/A"
                NotificationEventService(self.db).notify_content_suggestions_ready(
                    user_id=audience.user_id,
                    audience_id=audience_id,
                    audience_name=audience.name,
                    analysis_id=analysis_id,
                    suggestion_count=len(verified),
                    metadata_extra={
                        "top_suggestion_title": top_title,
                        "modules_used": modules_available,
                    },
                )
            except Exception:
                logger.debug("Failed to send notification for content suggestions")

            return True

        except Exception as e:
            logger.exception(
                "Content suggestion generation failed for audience %s", audience_id
            )
            try:
                self.suggestion_repo.mark_failed(analysis_id, str(e))
            except Exception:
                pass
            try:
                audience = self.audience_repo.find_by_id(audience_id)
                if audience:
                    from app.modules.notifications.application.services.notification_event_service import (
                        NotificationEventService,
                    )

                    NotificationEventService(self.db).notify_content_suggestions_failed(
                        user_id=audience.user_id,
                        audience_id=audience_id,
                        audience_name=audience.name,
                        analysis_id=analysis_id,
                        error=str(e),
                    )
            except Exception:
                pass
            return False
