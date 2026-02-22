"""Triggers behavioral pattern analysis in background when user requests it."""

import logging
import threading
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.topic_behavioral_patterns.infra.repositories.topic_behavioral_pattern_repository import (
    TopicBehavioralPatternRepository,
)
from app.modules.audience_topics.infra.repositories.audience_topic_repository import (
    AudienceTopicRepository,
)
from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)

logger = logging.getLogger(__name__)


class TriggerBehavioralPatternUseCase:
    """
    Verifica se a análise de padrões comportamentais precisa ser processada
    e dispara em background thread se necessário.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.topic_repo = AudienceTopicRepository(db)
        self.pattern_repo = TopicBehavioralPatternRepository(db)

    def execute(self, topic_id: UUID, audience_id: UUID, force: bool = False) -> dict:
        """
        Verifica e dispara análise de padrões comportamentais se necessário.

        Args:
            topic_id: ID do tópico
            audience_id: ID da audiência
            force: Se True, ignora fingerprint e força reprocessamento

        Returns:
            dict com status e informações
        """
        topic = self.topic_repo.get_topic_by_id(topic_id)
        if not topic:
            return {"status": "error", "message": "Topic not found"}

        latest = self.pattern_repo.find_latest_by_topic(topic_id)
        if latest and latest.status == "processing" and not force:
            return {
                "status": "processing",
                "message": "Já existe uma análise em andamento.",
                "analysis_id": str(latest.id),
            }

        communities = self.audience_repo.get_communities(audience_id)
        community_names = [c.subreddit_name for c in communities]
        fingerprint = TopicBehavioralPatternRepository.generate_fingerprint(
            topic_id, community_names
        )

        if not force:
            existing = self.pattern_repo.find_by_fingerprint(topic_id, fingerprint)
            if existing:
                return {
                    "status": existing.status,
                    "message": f"Análise existente (status={existing.status}).",
                    "analysis_id": str(existing.id),
                }

        analysis = self.pattern_repo.create_analysis(topic_id, audience_id, fingerprint)
        logger.info(
            "Triggering behavioral pattern analysis for topic %s (analysis %s)",
            topic_id,
            analysis.id,
        )

        self._run_in_background(topic_id, audience_id, analysis.id)

        return {
            "status": "processing",
            "message": "Análise de padrões comportamentais iniciada. Consulte novamente em alguns minutos.",
            "analysis_id": str(analysis.id),
        }

    def _run_in_background(
        self, topic_id: UUID, audience_id: UUID, analysis_id: UUID
    ) -> None:
        """Dispara detecção de padrões comportamentais em background thread."""
        from app.modules.shared.infra.database.database import SessionLocal

        def background_task():
            db = SessionLocal()
            try:
                from app.modules.topic_behavioral_patterns.application.use_cases.detect_behavioral_patterns_use_case.detect_behavioral_patterns_use_case import (
                    DetectBehavioralPatternsUseCase,
                )

                use_case = DetectBehavioralPatternsUseCase(db)
                use_case.execute(topic_id, audience_id, analysis_id)
            except Exception:
                logger.exception(
                    "Background behavioral pattern analysis failed for topic %s", topic_id
                )
            finally:
                db.close()

        thread = threading.Thread(target=background_task, daemon=True)
        thread.start()
