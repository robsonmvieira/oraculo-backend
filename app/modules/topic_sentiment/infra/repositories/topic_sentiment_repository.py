import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.topic_sentiment.domain.entities.topic_sentiment import (
    TopicSentiment,
    TopicSentimentAnalysis,
)


class TopicSentimentRepository:
    """Repositório para operações com análises de sentimento de tópicos."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def generate_fingerprint(topic_id: UUID, community_names: list[str]) -> str:
        """Gera fingerprint SHA256 do tópico + comunidades."""
        sorted_names = sorted(n.lower() for n in community_names)
        content = f"{topic_id}:" + ":".join(sorted_names)
        return hashlib.sha256(content.encode()).hexdigest()

    def find_latest_by_topic(self, topic_id: UUID) -> TopicSentimentAnalysis | None:
        """Busca a análise mais recente de sentimento (qualquer status)."""
        return (
            self.db.query(TopicSentimentAnalysis)
            .filter(TopicSentimentAnalysis.topic_id == topic_id)
            .order_by(TopicSentimentAnalysis.created_at.desc())
            .first()
        )

    def find_by_fingerprint(
        self, topic_id: UUID, fingerprint: str
    ) -> TopicSentimentAnalysis | None:
        """Busca análise por fingerprint (mesma composição)."""
        return (
            self.db.query(TopicSentimentAnalysis)
            .filter(
                TopicSentimentAnalysis.topic_id == topic_id,
                TopicSentimentAnalysis.topic_fingerprint == fingerprint,
                TopicSentimentAnalysis.status.in_(["ready", "processing"]),
            )
            .order_by(TopicSentimentAnalysis.created_at.desc())
            .first()
        )

    def create_analysis(
        self, topic_id: UUID, audience_id: UUID, fingerprint: str
    ) -> TopicSentimentAnalysis:
        """Cria um novo registro de análise com status 'processing'."""
        analysis = TopicSentimentAnalysis(
            topic_id=topic_id,
            audience_id=audience_id,
            topic_fingerprint=fingerprint,
            status="processing",
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def mark_ready(self, analysis_id: UUID) -> TopicSentimentAnalysis | None:
        """Marca análise como pronta."""
        analysis = (
            self.db.query(TopicSentimentAnalysis)
            .filter(TopicSentimentAnalysis.id == analysis_id)
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
    ) -> TopicSentimentAnalysis | None:
        """Marca análise como falha."""
        analysis = (
            self.db.query(TopicSentimentAnalysis)
            .filter(TopicSentimentAnalysis.id == analysis_id)
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

    def save_sentiment(self, analysis_id: UUID, data: dict) -> TopicSentiment:
        """Salva resultado da análise de sentimento."""
        sentiment = TopicSentiment(
            analysis_id=analysis_id,
            overall_sentiment=data.get("overall_sentiment"),
            emotional_map=data.get("emotional_map"),
            sentiment_by_community=data.get("sentiment_by_community"),
            sentiment_by_subtopic=data.get("sentiment_by_subtopic"),
            sentiment_drivers=data.get("sentiment_drivers"),
            tension_points=data.get("tension_points"),
            pain_points=data.get("pain_points"),
            sentiment_opportunities=data.get("sentiment_opportunities"),
        )
        self.db.add(sentiment)
        self.db.commit()
        self.db.refresh(sentiment)
        return sentiment

    def get_sentiment(self, analysis_id: UUID) -> TopicSentiment | None:
        """Busca o sentimento de uma análise."""
        return (
            self.db.query(TopicSentiment)
            .filter(TopicSentiment.analysis_id == analysis_id)
            .first()
        )

    def delete_old_analyses(self, topic_id: UUID, keep_latest: int = 2) -> int:
        """Remove análises antigas, mantendo as N mais recentes."""
        latest_ids = (
            self.db.query(TopicSentimentAnalysis.id)
            .filter(TopicSentimentAnalysis.topic_id == topic_id)
            .order_by(TopicSentimentAnalysis.created_at.desc())
            .limit(keep_latest)
            .all()
        )
        keep_ids = [row[0] for row in latest_ids]

        if not keep_ids:
            return 0

        deleted = (
            self.db.query(TopicSentimentAnalysis)
            .filter(
                TopicSentimentAnalysis.topic_id == topic_id,
                TopicSentimentAnalysis.id.notin_(keep_ids),
            )
            .delete(synchronize_session="fetch")
        )
        self.db.commit()
        return deleted
