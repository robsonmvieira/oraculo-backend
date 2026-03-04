"""Use case para disparar análise de Product Intelligence."""

import logging
import threading
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.product_intelligence.infra.repositories.product_intelligence_repository import (
    ProductIntelligenceRepository,
)

logger = logging.getLogger(__name__)


class TriggerProductIntelligenceUseCase:
    """
    Verifica se a análise de product intelligence precisa ser processada
    e dispara em background thread se necessário.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.pi_repo = ProductIntelligenceRepository(db)

    def execute(
        self,
        audience_id: UUID,
        window: str = "week",
        language: str = "en",
    ) -> dict:
        """
        Valida e dispara análise de product intelligence.
        Retorna dict com status e analysis_id.
        """
        communities = self.audience_repo.get_communities(audience_id)
        community_names = [c.subreddit_name for c in communities]

        if not community_names:
            return {
                "status": "failed",
                "message": "No communities in audience",
            }

        # Gerar fingerprint com período
        fingerprint = ProductIntelligenceRepository.generate_fingerprint(
            audience_id, community_names, window
        )

        # Verificar se já existe análise para este período
        existing = self.pi_repo.find_by_fingerprint(audience_id, fingerprint)
        if existing:
            if existing.status == "processing":
                return {
                    "status": "processing",
                    "message": "Product intelligence analysis already in progress.",
                    "analysis_id": str(existing.id),
                }
            if existing.status == "ready":
                return {
                    "status": "already_exists",
                    "message": "Product intelligence analysis already exists for this period.",
                    "analysis_id": str(existing.id),
                }

        # Criar registro de análise
        analysis = self.pi_repo.create_analysis(
            audience_id=audience_id,
            fingerprint=fingerprint,
        )
        logger.info(
            "Triggering product intelligence analysis for audience %s (analysis %s)",
            audience_id,
            analysis.id,
        )

        # Disparar em background
        self._run_in_background(audience_id, analysis.id, window, language)

        return {
            "status": "processing",
            "message": "Product intelligence analysis started. Check back in a few minutes.",
            "analysis_id": str(analysis.id),
        }

    def _run_in_background(
        self,
        audience_id: UUID,
        analysis_id: UUID,
        window: str,
        language: str = "en",
    ) -> None:
        """Dispara extração em background thread."""
        from app.modules.shared.infra.database.database import SessionLocal

        def background_task():
            db = SessionLocal()
            try:
                from app.modules.product_intelligence.application.use_cases.extract_product_intelligence_use_case.extract_product_intelligence_use_case import (
                    ExtractProductIntelligenceUseCase,
                )

                use_case = ExtractProductIntelligenceUseCase(db)
                use_case.execute(audience_id, analysis_id, window, language=language)
            except Exception:
                logger.exception(
                    "Background product intelligence failed for audience %s",
                    audience_id,
                )
            finally:
                db.close()

        thread = threading.Thread(target=background_task, daemon=True)
        thread.start()
