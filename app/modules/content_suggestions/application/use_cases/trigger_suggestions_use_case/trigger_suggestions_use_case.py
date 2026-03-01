"""Use case para disparar geração de sugestões de conteúdo em background."""

import logging
import threading
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.content_suggestions.application.use_cases.generate_suggestions_use_case.context_builder import (
    ContextBuilder,
)
from app.modules.content_suggestions.infra.repositories.content_suggestion_repository import (
    ContentSuggestionRepository,
)

logger = logging.getLogger(__name__)


class TriggerSuggestionsUseCase:
    """
    Verifica se a geração de sugestões precisa ser processada
    e dispara em background thread se necessário.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.suggestion_repo = ContentSuggestionRepository(db)

    def execute(
        self,
        audience_id: UUID,
        user_id: UUID,
        language: str = "en",
    ) -> dict:
        """
        Valida e dispara geração de sugestões.

        Returns:
            dict com status e informações
        """
        # 1. Validar audiência
        audience = self.audience_repo.find_by_id(audience_id)
        if not audience:
            return {"status": "error", "message": "Audience not found"}

        # 2. Montar contexto para gerar fingerprint
        builder = ContextBuilder(self.db)
        _, modules_available, topic_contexts, analysis_ids = builder.build(audience_id)

        if not topic_contexts:
            return {
                "status": "error",
                "message": "No topic analysis available. Run topic analysis first.",
            }

        # 3. Gerar fingerprint multi-módulo
        fingerprint = ContentSuggestionRepository.generate_fingerprint(analysis_ids)

        # 4. Verificar se já existe
        existing = self.suggestion_repo.find_by_fingerprint(audience_id, fingerprint)
        if existing:
            if existing.status == "processing":
                return {
                    "status": "processing",
                    "message": "Content suggestions are already being generated.",
                    "analysis_id": str(existing.id),
                }
            if existing.status == "ready":
                return {
                    "status": "already_exists",
                    "analysis_id": str(existing.id),
                    "message": "Suggestions already generated for current data. Run new analyses first to get updated suggestions.",
                }

        # 5. Criar registro de análise
        analysis = self.suggestion_repo.create_analysis(
            audience_id=audience_id,
            user_id=user_id,
            fingerprint=fingerprint,
        )

        logger.info(
            "Triggering content suggestions for audience %s (analysis %s, %d modules)",
            audience_id,
            analysis.id,
            len(modules_available),
        )

        # 6. Disparar em background
        self._run_in_background(audience_id, analysis.id, language)

        return {
            "status": "processing",
            "analysis_id": str(analysis.id),
            "message": "Content suggestions are being generated. You will be notified when ready.",
            "modules_found": modules_available,
        }

    def _run_in_background(
        self,
        audience_id: UUID,
        analysis_id: UUID,
        language: str = "en",
    ) -> None:
        """Dispara geração de sugestões em background thread."""
        from app.modules.shared.infra.database.database import SessionLocal

        def background_task():
            db = SessionLocal()
            try:
                from app.modules.content_suggestions.application.use_cases.generate_suggestions_use_case.generate_suggestions_use_case import (
                    GenerateSuggestionsUseCase,
                )

                use_case = GenerateSuggestionsUseCase(db)
                use_case.execute(audience_id, analysis_id, language=language)
            except Exception:
                logger.exception(
                    "Background content suggestion generation failed for audience %s",
                    audience_id,
                )
            finally:
                db.close()

        thread = threading.Thread(target=background_task, daemon=True)
        thread.start()
