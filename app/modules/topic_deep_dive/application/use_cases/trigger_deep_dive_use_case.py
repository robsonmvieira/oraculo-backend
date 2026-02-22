"""Triggers deep dive analysis in background when user requests it."""

import logging
import threading
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.topic_deep_dive.infra.repositories.topic_deep_dive_repository import (
    TopicDeepDiveRepository,
)
from app.modules.audience_topics.infra.repositories.audience_topic_repository import (
    AudienceTopicRepository,
)
from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)

logger = logging.getLogger(__name__)


class TriggerDeepDiveUseCase:
    """
    Verifica se o deep dive precisa ser processado
    e dispara em background thread se necessário.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.topic_repo = AudienceTopicRepository(db)
        self.deep_dive_repo = TopicDeepDiveRepository(db)

    def execute(self, topic_id: UUID, audience_id: UUID, force: bool = False) -> dict:
        """
        Verifica e dispara deep dive se necessário.

        Args:
            topic_id: ID do tópico
            audience_id: ID da audiência
            force: Se True, ignora fingerprint e força reprocessamento

        Returns:
            dict com status e informações
        """
        # Verificar se o tópico existe
        topic = self.topic_repo.get_topic_by_id(topic_id)
        if not topic:
            return {"status": "error", "message": "Topic not found"}

        # Verificar se já há análise em processamento
        latest = self.deep_dive_repo.find_latest_by_topic(topic_id)
        if latest and latest.status == "processing" and not force:
            return {
                "status": "processing",
                "message": "Já existe uma análise em andamento.",
                "analysis_id": str(latest.id),
            }

        # Gerar fingerprint
        communities = self.audience_repo.get_communities(audience_id)
        community_names = [c.subreddit_name for c in communities]
        fingerprint = TopicDeepDiveRepository.generate_fingerprint(topic_id, community_names)

        # Se não forçar, verificar se já existe análise com mesmo fingerprint
        if not force:
            existing = self.deep_dive_repo.find_by_fingerprint(topic_id, fingerprint)
            if existing:
                return {
                    "status": existing.status,
                    "message": f"Análise existente (status={existing.status}).",
                    "analysis_id": str(existing.id),
                }

        # Criar registro de análise com status "processing"
        analysis = self.deep_dive_repo.create_analysis(topic_id, audience_id, fingerprint)
        logger.info(
            "Triggering deep dive for topic %s (analysis %s)",
            topic_id,
            analysis.id,
        )

        # Disparar em background
        self._run_in_background(topic_id, audience_id, analysis.id)

        return {
            "status": "processing",
            "message": "Análise de deep dive iniciada. Consulte novamente em alguns minutos.",
            "analysis_id": str(analysis.id),
        }

    def _run_in_background(
        self, topic_id: UUID, audience_id: UUID, analysis_id: UUID
    ) -> None:
        """Dispara extração de deep dive em background thread."""
        from app.modules.shared.infra.database.database import SessionLocal

        def background_task():
            db = SessionLocal()
            try:
                from app.modules.topic_deep_dive.application.use_cases.extract_deep_dive_use_case.extract_deep_dive_use_case import (
                    ExtractDeepDiveUseCase,
                )

                use_case = ExtractDeepDiveUseCase(db)
                use_case.execute(topic_id, audience_id, analysis_id)
            except Exception:
                logger.exception(
                    "Background deep dive failed for topic %s", topic_id
                )
            finally:
                db.close()

        thread = threading.Thread(target=background_task, daemon=True)
        thread.start()
