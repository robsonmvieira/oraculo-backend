"""Returns growth history for a topic with calculated trends."""

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


class GetGrowthHistoryUseCase:
    """
    Retorna historico de crescimento de um topico com trend calculado.
    """

    def __init__(self, db: Session):
        self.db = db
        self.topic_repo = AudienceTopicRepository(db)
        self.snapshot_repo = TopicSnapshotRepository(db)

    def execute(self, audience_id: UUID, topic_id: UUID) -> dict:
        """
        Busca historico de crescimento de um topico.

        Args:
            audience_id: ID da audiencia
            topic_id: ID do topico atual

        Returns:
            dict com current, history, trend e total_snapshots
        """
        # Buscar topico atual
        topic = self.topic_repo.get_topic_by_id(topic_id)
        if not topic:
            return {"error": "Topic not found"}

        topic_name_normalized = TopicSnapshotRepository.normalize_topic_name(topic.name)

        # Buscar snapshots historicos
        snapshots = self.snapshot_repo.get_history_by_topic(
            audience_id=audience_id,
            topic_name_normalized=topic_name_normalized,
            limit=12,
        )

        # Calcular crescimento real se houver snapshots
        growth_data = self.snapshot_repo.calculate_real_growth(
            audience_id=audience_id,
            topic_name_normalized=topic_name_normalized,
        )

        # Dados atuais do topico
        if growth_data:
            current_growth = growth_data["growth_percentage"]
            growth_source = "calculated"
            trend = growth_data["trend"]
        else:
            current_growth = topic.growth_percentage
            growth_source = "estimated"
            trend = None

        current = {
            "mention_frequency": topic.mention_frequency,
            "post_count": topic.post_count,
            "growth_percentage": current_growth,
            "growth_source": growth_source,
            "snapshot_date": snapshots[0].snapshot_date.isoformat() if snapshots else None,
        }

        # Construir historico a partir dos snapshots
        history = []
        for i, snap in enumerate(snapshots):
            # Calcular crescimento entre snapshots consecutivos
            snap_growth = None
            snap_source = "estimated"
            if i + 1 < len(snapshots):
                prev = snapshots[i + 1]
                if prev.mention_frequency and prev.mention_frequency > 0:
                    snap_growth = round(
                        ((snap.mention_frequency - prev.mention_frequency)
                         / prev.mention_frequency) * 100,
                        1,
                    )
                    snap_source = "calculated"
                elif snap.mention_frequency and snap.mention_frequency > 0:
                    snap_growth = 100.0
                    snap_source = "calculated"
            else:
                # Snapshot mais antigo — usa estimativa original
                snap_growth = snap.growth_percentage
                snap_source = "estimated"

            history.append({
                "mention_frequency": snap.mention_frequency,
                "post_count": snap.post_count,
                "growth_percentage": snap_growth,
                "growth_source": snap_source,
                "snapshot_date": snap.snapshot_date.isoformat(),
            })

        return {
            "topic_id": str(topic.id),
            "topic_name": topic.name,
            "current": current,
            "history": history,
            "trend": trend,
            "total_snapshots": len(snapshots),
        }
