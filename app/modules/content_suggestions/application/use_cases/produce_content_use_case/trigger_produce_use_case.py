"""Use case para disparar producao de conteudo em background."""

import logging
import threading
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.content_suggestions.infra.repositories.content_draft_repository import (
    ContentDraftRepository,
)
from app.modules.content_suggestions.infra.repositories.content_suggestion_repository import (
    ContentSuggestionRepository,
)

logger = logging.getLogger(__name__)

VALID_PLATFORMS = ("linkedin", "twitter", "instagram", "reddit")


class TriggerProduceUseCase:
    """
    Valida a sugestao e plataformas, e dispara producao em background.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.suggestion_repo = ContentSuggestionRepository(db)
        self.draft_repo = ContentDraftRepository(db)

    def execute(
        self,
        audience_id: UUID,
        suggestion_id: UUID,
        target_platforms: list[str],
        language: str = "en",
    ) -> dict:
        """
        Valida e dispara producao de conteudo.

        Returns:
            dict com status e informacoes
        """
        # 1. Validar plataformas
        invalid = [p for p in target_platforms if p not in VALID_PLATFORMS]
        if invalid:
            return {
                "status": "error",
                "message": f"Invalid platforms: {', '.join(invalid)}. Valid: {', '.join(VALID_PLATFORMS)}",
            }

        if not target_platforms:
            return {"status": "error", "message": "At least one platform is required."}

        # 2. Validar sugestao
        suggestion = self.suggestion_repo.get_suggestion_by_id(suggestion_id)
        if not suggestion:
            return {"status": "error", "message": "Suggestion not found."}

        # 3. Verificar se pertence a audiencia
        if str(suggestion.analysis.audience_id) != str(audience_id):
            return {"status": "error", "message": "Suggestion does not belong to this audience."}

        # 4. Verificar se ja tem drafts
        existing_drafts = self.draft_repo.get_drafts_by_suggestion(suggestion_id)
        existing_platforms = {d.platform for d in existing_drafts if d.status == "ready"}
        new_platforms = [p for p in target_platforms if p not in existing_platforms]

        if not new_platforms:
            return {
                "status": "already_exists",
                "message": "Drafts already exist for all requested platforms.",
                "suggestion_id": str(suggestion_id),
                "platforms": list(existing_platforms),
            }

        logger.info(
            "Triggering content production for suggestion %s on %s",
            suggestion_id,
            new_platforms,
        )

        # 5. Disparar em background
        self._run_in_background(suggestion_id, new_platforms, language)

        return {
            "status": "processing",
            "suggestion_id": str(suggestion_id),
            "platforms": new_platforms,
            "message": "Content production started. You will be notified when ready.",
        }

    def _run_in_background(
        self,
        suggestion_id: UUID,
        target_platforms: list[str],
        language: str = "en",
    ) -> None:
        """Dispara producao em background thread."""
        from app.modules.shared.infra.database.database import SessionLocal

        def background_task():
            db = SessionLocal()
            try:
                from app.modules.content_suggestions.application.use_cases.produce_content_use_case.produce_content_use_case import (
                    ProduceContentUseCase,
                )

                use_case = ProduceContentUseCase(db)
                use_case.execute(suggestion_id, target_platforms, language=language)
            except Exception:
                logger.exception(
                    "Background content production failed for suggestion %s",
                    suggestion_id,
                )
            finally:
                db.close()

        thread = threading.Thread(target=background_task, daemon=True)
        thread.start()
