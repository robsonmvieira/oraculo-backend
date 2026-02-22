import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.topic_deep_dive.domain.entities.topic_deep_dive import (
    TopicDeepDive,
    TopicDeepDiveAnalysis,
)


class TopicDeepDiveRepository:
    """Repositório para operações com análises de deep dive de tópicos."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def generate_fingerprint(topic_id: UUID, community_names: list[str]) -> str:
        """Gera fingerprint SHA256 do tópico + comunidades."""
        sorted_names = sorted(n.lower() for n in community_names)
        content = f"{topic_id}:" + ":".join(sorted_names)
        return hashlib.sha256(content.encode()).hexdigest()

    def find_latest_by_topic(self, topic_id: UUID) -> TopicDeepDiveAnalysis | None:
        """Busca a análise mais recente de deep dive (qualquer status)."""
        return (
            self.db.query(TopicDeepDiveAnalysis)
            .filter(TopicDeepDiveAnalysis.topic_id == topic_id)
            .order_by(TopicDeepDiveAnalysis.created_at.desc())
            .first()
        )

    def find_by_fingerprint(
        self, topic_id: UUID, fingerprint: str
    ) -> TopicDeepDiveAnalysis | None:
        """Busca análise por fingerprint (mesma composição)."""
        return (
            self.db.query(TopicDeepDiveAnalysis)
            .filter(
                TopicDeepDiveAnalysis.topic_id == topic_id,
                TopicDeepDiveAnalysis.topic_fingerprint == fingerprint,
                TopicDeepDiveAnalysis.status.in_(["ready", "processing"]),
            )
            .order_by(TopicDeepDiveAnalysis.created_at.desc())
            .first()
        )

    def create_analysis(
        self, topic_id: UUID, audience_id: UUID, fingerprint: str
    ) -> TopicDeepDiveAnalysis:
        """Cria um novo registro de análise com status 'processing'."""
        analysis = TopicDeepDiveAnalysis(
            topic_id=topic_id,
            audience_id=audience_id,
            topic_fingerprint=fingerprint,
            status="processing",
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def mark_ready(self, analysis_id: UUID) -> TopicDeepDiveAnalysis | None:
        """Marca análise como pronta."""
        analysis = (
            self.db.query(TopicDeepDiveAnalysis)
            .filter(TopicDeepDiveAnalysis.id == analysis_id)
            .first()
        )
        if not analysis:
            return None

        analysis.status = "ready"
        analysis.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def mark_failed(
        self, analysis_id: UUID, error_message: str
    ) -> TopicDeepDiveAnalysis | None:
        """Marca análise como falha."""
        analysis = (
            self.db.query(TopicDeepDiveAnalysis)
            .filter(TopicDeepDiveAnalysis.id == analysis_id)
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

    def save_deep_dive(self, analysis_id: UUID, data: dict) -> TopicDeepDive:
        """Salva resultado do deep dive."""
        deep_dive = TopicDeepDive(
            analysis_id=analysis_id,
            summary=data.get("summary"),
            subtopics=data.get("subtopics"),
            common_questions=data.get("common_questions"),
            sentiment=data.get("sentiment"),
            mentioned_products=data.get("mentioned_products"),
            representative_posts=data.get("representative_posts"),
            actionable_insights=data.get("actionable_insights"),
        )
        self.db.add(deep_dive)
        self.db.commit()
        self.db.refresh(deep_dive)
        return deep_dive

    def get_deep_dive(self, analysis_id: UUID) -> TopicDeepDive | None:
        """Busca o deep dive de uma análise."""
        return (
            self.db.query(TopicDeepDive)
            .filter(TopicDeepDive.analysis_id == analysis_id)
            .first()
        )

    def delete_old_analyses(self, topic_id: UUID, keep_latest: int = 2) -> int:
        """Remove análises antigas, mantendo as N mais recentes."""
        latest_ids = (
            self.db.query(TopicDeepDiveAnalysis.id)
            .filter(TopicDeepDiveAnalysis.topic_id == topic_id)
            .order_by(TopicDeepDiveAnalysis.created_at.desc())
            .limit(keep_latest)
            .all()
        )
        keep_ids = [row[0] for row in latest_ids]

        if not keep_ids:
            return 0

        deleted = (
            self.db.query(TopicDeepDiveAnalysis)
            .filter(
                TopicDeepDiveAnalysis.topic_id == topic_id,
                TopicDeepDiveAnalysis.id.notin_(keep_ids),
            )
            .delete(synchronize_session="fetch")
        )
        self.db.commit()
        return deleted
