"""Triggers keyword analysis in background when audience communities change."""

import logging
import threading
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audience_keywords.infra.repositories.audience_keyword_repository import (
    AudienceKeywordRepository,
)
from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)

logger = logging.getLogger(__name__)


class TriggerKeywordAnalysisUseCase:
    """
    Verifica se a análise de keywords precisa ser reprocessada
    e dispara em background thread se necessário.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.keyword_repo = AudienceKeywordRepository(db)

    def execute(self, audience_id: UUID, language: str = "en") -> None:
        """
        Verifica e dispara análise se necessário.
        Não bloqueia — retorna imediatamente.
        """
        communities = self.audience_repo.get_communities(audience_id)
        community_names = [c.subreddit_name for c in communities]

        if not community_names:
            logger.info("Skipping keyword analysis — no communities in audience %s", audience_id)
            return

        # Gerar fingerprint da composição atual
        fingerprint = AudienceKeywordRepository.generate_fingerprint(community_names)

        # Verificar se já existe análise com mesmo fingerprint (ready ou processing)
        existing = self.keyword_repo.find_by_fingerprint(audience_id, fingerprint)
        if existing:
            logger.info(
                "Skipping keyword analysis — existing analysis (status=%s) for audience %s",
                existing.status,
                audience_id,
            )
            return

        # Criar registro de análise com status "processing"
        analysis = self.keyword_repo.create_analysis(audience_id, fingerprint)
        logger.info(
            "Triggering keyword analysis for audience %s (analysis %s)",
            audience_id,
            analysis.id,
        )

        # Disparar em background
        self._run_in_background(audience_id, analysis.id, language)

    def _run_in_background(self, audience_id: UUID, analysis_id: UUID, language: str = "en") -> None:
        """Dispara extração de keywords em background thread."""
        from app.modules.shared.infra.database.database import SessionLocal

        def background_task():
            db = SessionLocal()
            try:
                from app.modules.audience_keywords.application.use_cases.extract_keywords_use_case.extract_keywords_use_case import (
                    ExtractKeywordsUseCase,
                )

                use_case = ExtractKeywordsUseCase(db)
                use_case.execute(audience_id, analysis_id, language=language)
            except Exception:
                logger.exception(
                    "Background keyword extraction failed for audience %s", audience_id
                )
            finally:
                db.close()

        thread = threading.Thread(target=background_task, daemon=True)
        thread.start()
