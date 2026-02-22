"""Triggers cross-topic pattern analysis in background when user requests it."""

import logging
import threading
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.topic_patterns.infra.repositories.topic_pattern_repository import (
    TopicPatternRepository,
)
from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)

logger = logging.getLogger(__name__)


class TriggerPatternAnalysisUseCase:
    """
    Verifica se a analise de padroes precisa ser processada
    e dispara em background thread se necessario.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.pattern_repo = TopicPatternRepository(db)

    def execute(self, audience_id: UUID, force: bool = False) -> dict:
        """
        Verifica e dispara deteccao de padroes se necessario.

        Args:
            audience_id: ID da audiencia
            force: Se True, ignora fingerprint e forca reprocessamento

        Returns:
            dict com status e informacoes
        """
        # Verificar se ja ha analise em processamento
        latest = self.pattern_repo.find_latest_by_audience(audience_id)
        if latest and latest.status == "processing" and not force:
            return {
                "status": "processing",
                "message": "Ja existe uma analise em andamento.",
                "analysis_id": str(latest.id),
            }

        # Gerar fingerprint
        communities = self.audience_repo.get_communities(audience_id)
        community_names = [c.subreddit_name for c in communities]
        fingerprint = TopicPatternRepository.generate_fingerprint(
            audience_id, community_names
        )

        # Se nao forcar, verificar se ja existe analise com mesmo fingerprint
        if not force:
            existing = self.pattern_repo.find_by_fingerprint(audience_id, fingerprint)
            if existing:
                return {
                    "status": existing.status,
                    "message": f"Analise existente (status={existing.status}).",
                    "analysis_id": str(existing.id),
                }

        # Criar registro de analise com status "processing"
        analysis = self.pattern_repo.create_analysis(audience_id, fingerprint)
        logger.info(
            "Triggering pattern detection for audience %s (analysis %s)",
            audience_id,
            analysis.id,
        )

        # Disparar em background
        self._run_in_background(audience_id, analysis.id)

        return {
            "status": "processing",
            "message": "Analise de padroes iniciada. Consulte novamente em alguns minutos.",
            "analysis_id": str(analysis.id),
        }

    def _run_in_background(
        self, audience_id: UUID, analysis_id: UUID
    ) -> None:
        """Dispara deteccao de padroes em background thread."""
        from app.modules.shared.infra.database.database import SessionLocal

        def background_task():
            db = SessionLocal()
            try:
                from app.modules.topic_patterns.application.use_cases.detect_patterns_use_case.detect_patterns_use_case import (
                    DetectPatternsUseCase,
                )

                use_case = DetectPatternsUseCase(db)
                use_case.execute(audience_id, analysis_id)
            except Exception:
                logger.exception(
                    "Background pattern detection failed for audience %s",
                    audience_id,
                )
            finally:
                db.close()

        thread = threading.Thread(target=background_task, daemon=True)
        thread.start()
