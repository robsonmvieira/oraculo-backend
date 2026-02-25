"""Use case para disparar classificação de intenção em background."""

import logging
import threading
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.intent_classification.infra.repositories.intent_classification_repository import (
    IntentClassificationRepository,
)
from app.modules.theme_analysis.infra.repositories.theme_analysis_repository import (
    ThemeAnalysisRepository,
)

logger = logging.getLogger(__name__)


class TriggerIntentClassificationUseCase:
    """
    Verifica pré-requisitos e dispara classificação de intenção em background.
    Requer que exista uma theme_analysis com status 'ready' para a janela temporal.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.theme_repo = ThemeAnalysisRepository(db)
        self.intent_repo = IntentClassificationRepository(db)

    def execute(
        self,
        audience_id: UUID,
        window: str = "week",
        language: str = "en",
    ) -> dict:
        """
        Valida e dispara classificação de intenções.
        Retorna dict com status e analysis_id.
        """
        # 1. Buscar theme_analysis ready
        theme_analysis = self.theme_repo.find_latest_by_audience_and_window(
            audience_id, window
        )
        if not theme_analysis or theme_analysis.status != "ready":
            return {
                "status": "error",
                "message": "No theme analysis found for this period. Run theme analysis first.",
            }

        # 2. Gerar fingerprint baseado na theme_analysis
        fingerprint = IntentClassificationRepository.generate_fingerprint(
            theme_analysis.id
        )

        # 3. Verificar se já existe classificação
        existing = self.intent_repo.find_by_fingerprint(audience_id, fingerprint)
        if existing:
            if existing.status == "processing":
                return {
                    "status": "processing",
                    "message": "Classificação de intenções já em andamento.",
                    "analysis_id": str(existing.id),
                }
            if existing.status == "ready":
                return {
                    "status": "already_exists",
                    "message": "Classificação de intenções já existe para esta análise de temas.",
                    "analysis_id": str(existing.id),
                }

        # 4. Criar registro de classificação
        analysis = self.intent_repo.create_analysis(
            theme_analysis_id=theme_analysis.id,
            audience_id=audience_id,
            fingerprint=fingerprint,
            window=window,
        )
        logger.info(
            "Triggering intent classification (%s) for audience %s (analysis %s)",
            window,
            audience_id,
            analysis.id,
        )

        # 5. Disparar em background
        self._run_in_background(
            audience_id=audience_id,
            analysis_id=analysis.id,
            theme_analysis_id=theme_analysis.id,
            window=window,
            language=language,
        )

        return {
            "status": "processing",
            "message": f"Classificação de intenções ({window}) iniciada. Consulte novamente em alguns minutos.",
            "analysis_id": str(analysis.id),
        }

    def _run_in_background(
        self,
        audience_id: UUID,
        analysis_id: UUID,
        theme_analysis_id: UUID,
        window: str,
        language: str = "en",
    ) -> None:
        """Dispara classificação de intenções em background thread."""
        from app.modules.shared.infra.database.database import SessionLocal

        def background_task():
            db = SessionLocal()
            try:
                from app.modules.intent_classification.application.use_cases.classify_intents_use_case.classify_intents_use_case import (
                    ClassifyIntentsUseCase,
                )

                use_case = ClassifyIntentsUseCase(db)
                use_case.execute(
                    audience_id,
                    analysis_id,
                    theme_analysis_id,
                    window,
                    language=language,
                )
            except Exception:
                logger.exception(
                    "Background intent classification failed for audience %s",
                    audience_id,
                )
            finally:
                db.close()

        thread = threading.Thread(target=background_task, daemon=True)
        thread.start()
