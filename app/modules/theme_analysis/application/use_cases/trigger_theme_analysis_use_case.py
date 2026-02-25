"""Use case para disparar análise temporal de temas em background."""

import logging
import threading
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.theme_analysis.infra.repositories.theme_analysis_repository import (
    ThemeAnalysisRepository,
)

logger = logging.getLogger(__name__)


class TriggerThemeAnalysisUseCase:
    """
    Verifica se a análise de temas precisa ser processada
    e dispara em background thread se necessário.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.theme_repo = ThemeAnalysisRepository(db)

    def execute(
        self,
        audience_id: UUID,
        window: str = "week",
        language: str = "en",
    ) -> dict:
        """
        Valida e dispara análise de temas.
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
        fingerprint = ThemeAnalysisRepository.generate_fingerprint(
            audience_id, community_names, window
        )

        # Verificar se já existe análise para este período
        existing = self.theme_repo.find_by_fingerprint(audience_id, fingerprint)
        if existing:
            if existing.status == "processing":
                return {
                    "status": "processing",
                    "message": "Análise de temas já em andamento.",
                    "analysis_id": str(existing.id),
                }
            if existing.status == "ready":
                return {
                    "status": "already_exists",
                    "message": "Análise de temas já existe para este período.",
                    "analysis_id": str(existing.id),
                }

        # Calcular período
        period_start, period_end = ThemeAnalysisRepository.get_period_bounds(window)

        # Criar registro de análise
        analysis = self.theme_repo.create_analysis(
            audience_id=audience_id,
            fingerprint=fingerprint,
            window=window,
            period_start=period_start,
            period_end=period_end,
        )
        logger.info(
            "Triggering theme analysis (%s) for audience %s (analysis %s)",
            window,
            audience_id,
            analysis.id,
        )

        # Disparar em background
        self._run_in_background(audience_id, analysis.id, window, language)

        return {
            "status": "processing",
            "message": f"Análise de temas ({window}) iniciada. Consulte novamente em alguns minutos.",
            "analysis_id": str(analysis.id),
        }

    def _run_in_background(
        self,
        audience_id: UUID,
        analysis_id: UUID,
        window: str,
        language: str = "en",
    ) -> None:
        """Dispara extração de temas em background thread."""
        from app.modules.shared.infra.database.database import SessionLocal

        def background_task():
            db = SessionLocal()
            try:
                from app.modules.theme_analysis.application.use_cases.extract_themes_use_case.extract_themes_use_case import (
                    ExtractThemesUseCase,
                )

                use_case = ExtractThemesUseCase(db)
                use_case.execute(audience_id, analysis_id, window, language=language)
            except Exception:
                logger.exception(
                    "Background theme extraction failed for audience %s", audience_id
                )
            finally:
                db.close()

        thread = threading.Thread(target=background_task, daemon=True)
        thread.start()
