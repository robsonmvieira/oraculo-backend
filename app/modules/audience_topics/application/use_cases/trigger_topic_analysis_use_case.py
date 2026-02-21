"""Triggers topic analysis in background when audience communities change."""

import logging
import threading
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audience_topics.infra.repositories.audience_topic_repository import (
    AudienceTopicRepository,
)
from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)

logger = logging.getLogger(__name__)


class TriggerTopicAnalysisUseCase:
    """
    Verifica se a análise de tópicos precisa ser reprocessada
    e dispara em background thread se necessário.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.topic_repo = AudienceTopicRepository(db)

    def execute(self, audience_id: UUID) -> None:
        """
        Verifica e dispara análise se necessário.
        Não bloqueia — retorna imediatamente.
        """
        communities = self.audience_repo.get_communities(audience_id)
        community_names = [c.subreddit_name for c in communities]

        if not community_names:
            logger.info("Skipping topic analysis — no communities in audience %s", audience_id)
            return

        # Gerar fingerprint da composição atual
        fingerprint = AudienceTopicRepository.generate_fingerprint(community_names)

        # Verificar se já existe análise com mesmo fingerprint (ready ou processing)
        existing = self.topic_repo.find_by_fingerprint(audience_id, fingerprint)
        if existing:
            logger.info(
                "Skipping topic analysis — existing analysis (status=%s) for audience %s",
                existing.status,
                audience_id,
            )
            return

        # Criar registro de análise com status "processing"
        analysis = self.topic_repo.create_analysis(audience_id, fingerprint)
        logger.info(
            "Triggering topic analysis for audience %s (analysis %s)",
            audience_id,
            analysis.id,
        )

        # Disparar em background
        self._run_in_background(audience_id, analysis.id)

    def _run_in_background(self, audience_id: UUID, analysis_id: UUID) -> None:
        """Dispara extração de tópicos em background thread."""
        from app.modules.shared.infra.database.database import SessionLocal

        def background_task():
            db = SessionLocal()
            try:
                from app.modules.audience_topics.application.use_cases.extract_topics_use_case.extract_topics_use_case import (
                    ExtractTopicsUseCase,
                )

                use_case = ExtractTopicsUseCase(db)
                use_case.execute(audience_id, analysis_id)
            except Exception:
                logger.exception(
                    "Background topic extraction failed for audience %s", audience_id
                )
            finally:
                db.close()

        thread = threading.Thread(target=background_task, daemon=True)
        thread.start()
