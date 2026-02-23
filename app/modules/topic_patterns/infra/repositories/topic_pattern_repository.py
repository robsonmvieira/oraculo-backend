import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.topic_patterns.domain.entities.topic_pattern import (
    TopicPattern,
    TopicPatternAnalysis,
)


class TopicPatternRepository:
    """Repositorio para operacoes com analises de padroes cross-topic."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def generate_fingerprint(audience_id: UUID, community_names: list[str]) -> str:
        """Gera fingerprint SHA256 da audiencia + comunidades."""
        sorted_names = sorted(n.lower() for n in community_names)
        content = f"{audience_id}:" + ":".join(sorted_names)
        return hashlib.sha256(content.encode()).hexdigest()

    def find_latest_by_audience(self, audience_id: UUID) -> TopicPatternAnalysis | None:
        """Busca a analise mais recente de padroes (qualquer status)."""
        return (
            self.db.query(TopicPatternAnalysis)
            .filter(TopicPatternAnalysis.audience_id == audience_id)
            .order_by(TopicPatternAnalysis.created_at.desc())
            .first()
        )

    def find_by_fingerprint(
        self, audience_id: UUID, fingerprint: str
    ) -> TopicPatternAnalysis | None:
        """Busca analise por fingerprint (mesma composicao)."""
        return (
            self.db.query(TopicPatternAnalysis)
            .filter(
                TopicPatternAnalysis.audience_id == audience_id,
                TopicPatternAnalysis.communities_fingerprint == fingerprint,
                TopicPatternAnalysis.status.in_(["ready", "processing"]),
            )
            .order_by(TopicPatternAnalysis.created_at.desc())
            .first()
        )

    def create_analysis(
        self, audience_id: UUID, fingerprint: str
    ) -> TopicPatternAnalysis:
        """Cria um novo registro de analise com status 'processing'."""
        analysis = TopicPatternAnalysis(
            audience_id=audience_id,
            communities_fingerprint=fingerprint,
            status="processing",
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def mark_ready(self, analysis_id: UUID) -> TopicPatternAnalysis | None:
        """Marca analise como pronta."""
        analysis = (
            self.db.query(TopicPatternAnalysis)
            .filter(TopicPatternAnalysis.id == analysis_id)
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
    ) -> TopicPatternAnalysis | None:
        """Marca analise como falha."""
        analysis = (
            self.db.query(TopicPatternAnalysis)
            .filter(TopicPatternAnalysis.id == analysis_id)
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

    def save_pattern(self, analysis_id: UUID, data: dict) -> TopicPattern:
        """Salva resultado dos padroes detectados."""
        pattern = TopicPattern(
            analysis_id=analysis_id,
            summary=data.get("summary"),
            co_occurrences=data.get("co_occurrences"),
            unanswered_questions=data.get("unanswered_questions"),
            cross_community_gaps=data.get("cross_community_gaps"),
            content_opportunities=data.get("content_opportunities"),
        )
        self.db.add(pattern)
        self.db.commit()
        self.db.refresh(pattern)
        return pattern

    def get_pattern(self, analysis_id: UUID) -> TopicPattern | None:
        """Busca os padroes de uma analise."""
        return (
            self.db.query(TopicPattern)
            .filter(TopicPattern.analysis_id == analysis_id)
            .first()
        )

    def delete_old_analyses(self, audience_id: UUID, keep_latest: int = 2) -> int:
        """Remove analises antigas, mantendo as N mais recentes."""
        latest_ids = (
            self.db.query(TopicPatternAnalysis.id)
            .filter(TopicPatternAnalysis.audience_id == audience_id)
            .order_by(TopicPatternAnalysis.created_at.desc())
            .limit(keep_latest)
            .all()
        )
        keep_ids = [row[0] for row in latest_ids]

        if not keep_ids:
            return 0

        deleted = (
            self.db.query(TopicPatternAnalysis)
            .filter(
                TopicPatternAnalysis.audience_id == audience_id,
                TopicPatternAnalysis.id.notin_(keep_ids),
            )
            .delete(synchronize_session="fetch")
        )
        self.db.commit()
        return deleted
