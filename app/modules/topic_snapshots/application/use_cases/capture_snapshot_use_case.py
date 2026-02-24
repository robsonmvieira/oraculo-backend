"""Captures a snapshot of the current topic analysis before a new one runs."""

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audience_topics.infra.repositories.audience_topic_repository import (
    AudienceTopicRepository,
)
from app.modules.topic_snapshots.infra.repositories.topic_snapshot_repository import (
    TopicSnapshotRepository,
)

logger = logging.getLogger(__name__)


class CaptureSnapshotUseCase:
    """
    Captura snapshot dos topicos da analise 'ready' mais recente.
    Chamado pelo TriggerTopicAnalysisUseCase ANTES de disparar nova extracao.
    """

    def __init__(self, db: Session):
        self.db = db
        self.topic_repo = AudienceTopicRepository(db)
        self.snapshot_repo = TopicSnapshotRepository(db)

    def execute(self, audience_id: UUID) -> int:
        """
        Captura snapshot da analise ready mais recente.

        Args:
            audience_id: ID da audiencia

        Returns:
            Numero de snapshots criados (0 se nao houver analise ready)
        """
        # Buscar analise ready mais recente
        latest = self.topic_repo.find_latest_ready(audience_id)
        if not latest:
            logger.info(
                "No ready analysis found for audience %s — skipping snapshot",
                audience_id,
            )
            return 0

        # Buscar topicos da analise
        topics = self.topic_repo.get_topics(analysis_id=latest.id)
        if not topics:
            logger.info(
                "No topics in analysis %s — skipping snapshot",
                latest.id,
            )
            return 0

        # Capturar snapshot
        count = self.snapshot_repo.capture_snapshot(
            audience_id=audience_id,
            analysis_id=latest.id,
            topics=topics,
        )

        # Limpar snapshots antigos
        self.snapshot_repo.delete_old_snapshots(audience_id, keep_latest=12)

        return count
