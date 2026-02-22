import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.topic_behavioral_patterns.domain.entities.topic_behavioral_pattern import (
    TopicBehavioralPattern,
    TopicBehavioralPatternAnalysis,
)


class TopicBehavioralPatternRepository:
    """Repositório para operações com análises de padrões comportamentais de tópicos."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def generate_fingerprint(topic_id: UUID, community_names: list[str]) -> str:
        """Gera fingerprint SHA256 do tópico + comunidades."""
        sorted_names = sorted(n.lower() for n in community_names)
        content = f"{topic_id}:" + ":".join(sorted_names)
        return hashlib.sha256(content.encode()).hexdigest()

    def find_latest_by_topic(self, topic_id: UUID) -> TopicBehavioralPatternAnalysis | None:
        """Busca a análise mais recente de padrões comportamentais (qualquer status)."""
        return (
            self.db.query(TopicBehavioralPatternAnalysis)
            .filter(TopicBehavioralPatternAnalysis.topic_id == topic_id)
            .order_by(TopicBehavioralPatternAnalysis.created_at.desc())
            .first()
        )

    def find_by_fingerprint(
        self, topic_id: UUID, fingerprint: str
    ) -> TopicBehavioralPatternAnalysis | None:
        """Busca análise por fingerprint (mesma composição)."""
        return (
            self.db.query(TopicBehavioralPatternAnalysis)
            .filter(
                TopicBehavioralPatternAnalysis.topic_id == topic_id,
                TopicBehavioralPatternAnalysis.topic_fingerprint == fingerprint,
                TopicBehavioralPatternAnalysis.status.in_(["ready", "processing"]),
            )
            .order_by(TopicBehavioralPatternAnalysis.created_at.desc())
            .first()
        )

    def create_analysis(
        self, topic_id: UUID, audience_id: UUID, fingerprint: str
    ) -> TopicBehavioralPatternAnalysis:
        """Cria um novo registro de análise com status 'processing'."""
        analysis = TopicBehavioralPatternAnalysis(
            topic_id=topic_id,
            audience_id=audience_id,
            topic_fingerprint=fingerprint,
            status="processing",
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def mark_ready(self, analysis_id: UUID) -> TopicBehavioralPatternAnalysis | None:
        """Marca análise como pronta."""
        analysis = (
            self.db.query(TopicBehavioralPatternAnalysis)
            .filter(TopicBehavioralPatternAnalysis.id == analysis_id)
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
    ) -> TopicBehavioralPatternAnalysis | None:
        """Marca análise como falha."""
        analysis = (
            self.db.query(TopicBehavioralPatternAnalysis)
            .filter(TopicBehavioralPatternAnalysis.id == analysis_id)
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

    def save_behavioral_pattern(self, analysis_id: UUID, data: dict) -> TopicBehavioralPattern:
        """Salva resultado dos padrões comportamentais."""
        pattern = TopicBehavioralPattern(
            analysis_id=analysis_id,
            summary=data.get("summary"),
            tool_patterns=data.get("tool_patterns"),
            workaround_patterns=data.get("workaround_patterns"),
            friction_patterns=data.get("friction_patterns"),
            shift_patterns=data.get("shift_patterns"),
            demand_signals=data.get("demand_signals"),
        )
        self.db.add(pattern)
        self.db.commit()
        self.db.refresh(pattern)
        return pattern

    def get_behavioral_pattern(self, analysis_id: UUID) -> TopicBehavioralPattern | None:
        """Busca o padrão comportamental de uma análise."""
        return (
            self.db.query(TopicBehavioralPattern)
            .filter(TopicBehavioralPattern.analysis_id == analysis_id)
            .first()
        )

    def delete_old_analyses(self, topic_id: UUID, keep_latest: int = 2) -> int:
        """Remove análises antigas, mantendo as N mais recentes."""
        latest_ids = (
            self.db.query(TopicBehavioralPatternAnalysis.id)
            .filter(TopicBehavioralPatternAnalysis.topic_id == topic_id)
            .order_by(TopicBehavioralPatternAnalysis.created_at.desc())
            .limit(keep_latest)
            .all()
        )
        keep_ids = [row[0] for row in latest_ids]

        if not keep_ids:
            return 0

        deleted = (
            self.db.query(TopicBehavioralPatternAnalysis)
            .filter(
                TopicBehavioralPatternAnalysis.topic_id == topic_id,
                TopicBehavioralPatternAnalysis.id.notin_(keep_ids),
            )
            .delete(synchronize_session="fetch")
        )
        self.db.commit()
        return deleted
