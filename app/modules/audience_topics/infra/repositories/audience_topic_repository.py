import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audience_topics.domain.entities.audience_topic import (
    AudienceTopic,
    AudienceTopicAnalysis,
)


class AudienceTopicRepository:
    """Repositório para operações com análises de tópicos de audiências."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def generate_fingerprint(community_names: list[str]) -> str:
        """Gera fingerprint SHA256 das comunidades ordenadas."""
        sorted_names = sorted(n.lower() for n in community_names)
        content = ":".join(sorted_names)
        return hashlib.sha256(content.encode()).hexdigest()

    def find_latest_ready(self, audience_id: UUID) -> AudienceTopicAnalysis | None:
        """Busca a análise mais recente com status 'ready'."""
        return (
            self.db.query(AudienceTopicAnalysis)
            .filter(
                AudienceTopicAnalysis.audience_id == audience_id,
                AudienceTopicAnalysis.status == "ready",
            )
            .order_by(AudienceTopicAnalysis.created_at.desc())
            .first()
        )

    def find_latest_by_audience(self, audience_id: UUID) -> AudienceTopicAnalysis | None:
        """Busca a análise mais recente (qualquer status)."""
        return (
            self.db.query(AudienceTopicAnalysis)
            .filter(AudienceTopicAnalysis.audience_id == audience_id)
            .order_by(AudienceTopicAnalysis.created_at.desc())
            .first()
        )

    def find_by_fingerprint(
        self, audience_id: UUID, fingerprint: str
    ) -> AudienceTopicAnalysis | None:
        """Busca análise por fingerprint (mesma composição de comunidades)."""
        return (
            self.db.query(AudienceTopicAnalysis)
            .filter(
                AudienceTopicAnalysis.audience_id == audience_id,
                AudienceTopicAnalysis.communities_fingerprint == fingerprint,
                AudienceTopicAnalysis.status.in_(["ready", "processing"]),
            )
            .order_by(AudienceTopicAnalysis.created_at.desc())
            .first()
        )

    def create_analysis(
        self, audience_id: UUID, fingerprint: str
    ) -> AudienceTopicAnalysis:
        """Cria um novo registro de análise com status 'processing'."""
        analysis = AudienceTopicAnalysis(
            audience_id=audience_id,
            communities_fingerprint=fingerprint,
            status="processing",
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def mark_ready(
        self, analysis_id: UUID, total_topics: int
    ) -> AudienceTopicAnalysis | None:
        """Marca análise como pronta."""
        analysis = (
            self.db.query(AudienceTopicAnalysis)
            .filter(AudienceTopicAnalysis.id == analysis_id)
            .first()
        )
        if not analysis:
            return None

        analysis.status = "ready"
        analysis.total_topics = total_topics
        analysis.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def mark_failed(
        self, analysis_id: UUID, error_message: str
    ) -> AudienceTopicAnalysis | None:
        """Marca análise como falha."""
        analysis = (
            self.db.query(AudienceTopicAnalysis)
            .filter(AudienceTopicAnalysis.id == analysis_id)
            .first()
        )
        if not analysis:
            return None

        analysis.status = "failed"
        analysis.error_message = error_message
        analysis.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def save_topics(
        self, analysis_id: UUID, topics: list[dict]
    ) -> list[AudienceTopic]:
        """Salva lista de tópicos extraídos."""
        entities = []
        for topic_data in topics:
            topic = AudienceTopic(
                analysis_id=analysis_id,
                name=topic_data["name"],
                description=topic_data.get("description"),
                growth_percentage=topic_data.get("growth_percentage"),
                mention_frequency=topic_data.get("mention_frequency"),
                mention_period=topic_data.get("mention_period"),
                post_count=topic_data.get("post_count"),
                communities=topic_data.get("communities"),
                rank=topic_data.get("rank"),
            )
            self.db.add(topic)
            entities.append(topic)

        self.db.commit()
        return entities

    def get_topics(
        self,
        analysis_id: UUID,
        sort_by: str = "rank",
        limit: int = 200,
        offset: int = 0,
    ) -> list[AudienceTopic]:
        """Lista tópicos de uma análise com ordenação."""
        query = self.db.query(AudienceTopic).filter(
            AudienceTopic.analysis_id == analysis_id
        )

        if sort_by == "growth":
            query = query.order_by(AudienceTopic.growth_percentage.desc().nullslast())
        elif sort_by == "frequency":
            query = query.order_by(AudienceTopic.mention_frequency.desc().nullslast())
        elif sort_by == "name":
            query = query.order_by(AudienceTopic.name.asc())
        else:
            query = query.order_by(AudienceTopic.rank.asc().nullslast())

        return query.offset(offset).limit(limit).all()

    def get_topic_by_id(self, topic_id: UUID) -> AudienceTopic | None:
        """Busca um tópico por ID."""
        return (
            self.db.query(AudienceTopic)
            .filter(AudienceTopic.id == topic_id)
            .first()
        )

    def delete_old_analyses(self, audience_id: UUID, keep_latest: int = 2) -> int:
        """Remove análises antigas, mantendo as N mais recentes."""
        latest_ids = (
            self.db.query(AudienceTopicAnalysis.id)
            .filter(AudienceTopicAnalysis.audience_id == audience_id)
            .order_by(AudienceTopicAnalysis.created_at.desc())
            .limit(keep_latest)
            .all()
        )
        keep_ids = [row[0] for row in latest_ids]

        if not keep_ids:
            return 0

        deleted = (
            self.db.query(AudienceTopicAnalysis)
            .filter(
                AudienceTopicAnalysis.audience_id == audience_id,
                AudienceTopicAnalysis.id.notin_(keep_ids),
            )
            .delete(synchronize_session="fetch")
        )
        self.db.commit()
        return deleted
