"""Repository for topic snapshot operations."""

import logging
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.topic_snapshots.domain.entities.topic_snapshot import TopicSnapshot

logger = logging.getLogger(__name__)


class TopicSnapshotRepository:
    """Repositorio para operacoes com snapshots de topicos."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def normalize_topic_name(name: str) -> str:
        """Normaliza nome do topico para matching entre analises."""
        return name.strip().lower()

    def capture_snapshot(
        self,
        audience_id: UUID,
        analysis_id: UUID,
        topics: list,
    ) -> int:
        """
        Captura snapshot de todos os topicos de uma analise.

        Args:
            audience_id: ID da audiencia
            analysis_id: ID da analise sendo fotografada
            topics: Lista de objetos AudienceTopic

        Returns:
            Numero de snapshots criados
        """
        today = date.today()
        count = 0

        for topic in topics:
            snapshot = TopicSnapshot(
                audience_id=audience_id,
                analysis_id=analysis_id,
                topic_name=topic.name,
                topic_name_normalized=self.normalize_topic_name(topic.name),
                mention_frequency=topic.mention_frequency,
                mention_period=topic.mention_period,
                post_count=topic.post_count,
                growth_percentage=topic.growth_percentage,
                communities=topic.communities,
                snapshot_date=today,
            )
            self.db.add(snapshot)
            count += 1

        self.db.commit()
        logger.info(
            "Captured %d topic snapshots for audience %s (analysis %s)",
            count,
            audience_id,
            analysis_id,
        )
        return count

    def get_history_by_topic(
        self,
        audience_id: UUID,
        topic_name_normalized: str,
        limit: int = 12,
    ) -> list[TopicSnapshot]:
        """Retorna historico de snapshots de um topico, ordenado por data decrescente."""
        return (
            self.db.query(TopicSnapshot)
            .filter(
                TopicSnapshot.audience_id == audience_id,
                TopicSnapshot.topic_name_normalized == topic_name_normalized,
            )
            .order_by(TopicSnapshot.snapshot_date.desc())
            .limit(limit)
            .all()
        )

    def get_latest_snapshot(
        self,
        audience_id: UUID,
        topic_name_normalized: str,
    ) -> TopicSnapshot | None:
        """Retorna o snapshot mais recente de um topico."""
        return (
            self.db.query(TopicSnapshot)
            .filter(
                TopicSnapshot.audience_id == audience_id,
                TopicSnapshot.topic_name_normalized == topic_name_normalized,
            )
            .order_by(TopicSnapshot.snapshot_date.desc())
            .first()
        )

    def calculate_real_growth(
        self,
        audience_id: UUID,
        topic_name_normalized: str,
    ) -> dict | None:
        """
        Calcula crescimento real entre os 2 snapshots mais recentes.

        Returns:
            dict com growth_percentage e trend, ou None se nao houver 2+ snapshots
        """
        snapshots = (
            self.db.query(TopicSnapshot)
            .filter(
                TopicSnapshot.audience_id == audience_id,
                TopicSnapshot.topic_name_normalized == topic_name_normalized,
            )
            .order_by(TopicSnapshot.snapshot_date.desc())
            .limit(2)
            .all()
        )

        if len(snapshots) < 2:
            return None

        current = snapshots[0]
        previous = snapshots[1]

        # Calcular crescimento baseado em mention_frequency
        if previous.mention_frequency and previous.mention_frequency > 0:
            growth = (
                (current.mention_frequency - previous.mention_frequency)
                / previous.mention_frequency
            ) * 100
        elif current.mention_frequency and current.mention_frequency > 0:
            growth = 100.0
        else:
            growth = 0.0

        # Determinar trend
        if growth > 5:
            trend = "up"
        elif growth < -5:
            trend = "down"
        else:
            trend = "stable"

        return {
            "growth_percentage": round(growth, 1),
            "trend": trend,
        }

    def delete_old_snapshots(
        self,
        audience_id: UUID,
        keep_latest: int = 12,
    ) -> int:
        """
        Remove snapshots antigos de cada topico, mantendo os N mais recentes.

        Returns:
            Numero total de snapshots removidos
        """
        # Buscar nomes distintos de topicos
        distinct_names = (
            self.db.query(TopicSnapshot.topic_name_normalized)
            .filter(TopicSnapshot.audience_id == audience_id)
            .distinct()
            .all()
        )

        total_deleted = 0
        for (name,) in distinct_names:
            # IDs dos N mais recentes
            latest_ids = (
                self.db.query(TopicSnapshot.id)
                .filter(
                    TopicSnapshot.audience_id == audience_id,
                    TopicSnapshot.topic_name_normalized == name,
                )
                .order_by(TopicSnapshot.snapshot_date.desc())
                .limit(keep_latest)
                .all()
            )
            keep_ids = [row[0] for row in latest_ids]

            if not keep_ids:
                continue

            deleted = (
                self.db.query(TopicSnapshot)
                .filter(
                    TopicSnapshot.audience_id == audience_id,
                    TopicSnapshot.topic_name_normalized == name,
                    TopicSnapshot.id.notin_(keep_ids),
                )
                .delete(synchronize_session="fetch")
            )
            total_deleted += deleted

        if total_deleted > 0:
            self.db.commit()
            logger.info(
                "Deleted %d old snapshots for audience %s",
                total_deleted,
                audience_id,
            )

        return total_deleted
