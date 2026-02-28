"""Repositório para operações com classificações de intenção."""

import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.modules.intent_classification.domain.entities.intent_classification import (
    IntentClassificationAnalysis,
    IntentSummary,
    PostIntentClassification,
)


class IntentClassificationRepository:
    """Repositório para operações com classificações de intenção de posts."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def generate_fingerprint(theme_analysis_id: UUID) -> str:
        """Gera fingerprint SHA256 baseado no theme_analysis_id."""
        raw = str(theme_analysis_id)
        return hashlib.sha256(raw.encode()).hexdigest()

    def find_latest_by_audience_and_window(
        self, audience_id: UUID, window: str
    ) -> IntentClassificationAnalysis | None:
        """Busca a classificação mais recente para audiência e janela temporal."""
        return (
            self.db.query(IntentClassificationAnalysis)
            .filter(
                IntentClassificationAnalysis.audience_id == audience_id,
                IntentClassificationAnalysis.time_window == window,
            )
            .order_by(IntentClassificationAnalysis.created_at.desc())
            .first()
        )

    def find_by_fingerprint(
        self, audience_id: UUID, fingerprint: str
    ) -> IntentClassificationAnalysis | None:
        """Busca classificação por fingerprint (mesma theme_analysis fonte)."""
        return (
            self.db.query(IntentClassificationAnalysis)
            .filter(
                IntentClassificationAnalysis.audience_id == audience_id,
                IntentClassificationAnalysis.fingerprint == fingerprint,
                IntentClassificationAnalysis.status.in_(["ready", "processing"]),
            )
            .order_by(IntentClassificationAnalysis.created_at.desc())
            .first()
        )

    def create_analysis(
        self,
        theme_analysis_id: UUID,
        audience_id: UUID,
        fingerprint: str,
        window: str,
    ) -> IntentClassificationAnalysis:
        """Cria novo registro de classificação com status 'processing'."""
        analysis = IntentClassificationAnalysis(
            theme_analysis_id=theme_analysis_id,
            audience_id=audience_id,
            fingerprint=fingerprint,
            status="processing",
            time_window=window,
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def mark_ready(
        self, analysis_id: UUID, total_posts_classified: int
    ) -> IntentClassificationAnalysis | None:
        """Marca classificação como pronta."""
        analysis = (
            self.db.query(IntentClassificationAnalysis)
            .filter(IntentClassificationAnalysis.id == analysis_id)
            .first()
        )
        if not analysis:
            return None

        analysis.status = "ready"
        analysis.total_posts_classified = total_posts_classified
        analysis.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def mark_failed(
        self, analysis_id: UUID, error_message: str
    ) -> IntentClassificationAnalysis | None:
        """Marca classificação como falha."""
        analysis = (
            self.db.query(IntentClassificationAnalysis)
            .filter(IntentClassificationAnalysis.id == analysis_id)
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

    def save_post_classifications(
        self, analysis_id: UUID, classifications: list[dict]
    ) -> int:
        """Salva classificações individuais de posts."""
        for cls_data in classifications:
            classification = PostIntentClassification(
                analysis_id=analysis_id,
                post_reddit_id=cls_data["post_id"],
                post_title=cls_data["post_title"],
                post_subreddit=cls_data["post_subreddit"],
                primary_intent=cls_data["primary_intent"],
                secondary_intent=cls_data.get("secondary_intent"),
                confidence=cls_data.get("confidence", "medium"),
                sentiment=cls_data.get("sentiment"),
                topic_keyword=cls_data.get("topic_keyword"),
            )
            self.db.add(classification)
        self.db.commit()
        return len(classifications)

    def save_intent_summaries(self, analysis_id: UUID, summaries: list[dict]) -> int:
        """Salva resumos agregados por categoria de intenção."""
        for summary_data in summaries:
            summary = IntentSummary(
                analysis_id=analysis_id,
                intent_category=summary_data["category"],
                post_count=summary_data["post_count"],
                description=summary_data.get("description"),
                top_subreddits=summary_data.get("top_subreddits"),
                sample_posts=summary_data.get("sample_posts"),
                subcategories=summary_data.get("subcategories"),
                topic_keywords=summary_data.get("topic_keywords"),
                rank=summary_data.get("rank"),
            )
            self.db.add(summary)
        self.db.commit()
        return len(summaries)

    def get_intent_summaries(self, analysis_id: UUID) -> list[IntentSummary]:
        """Retorna resumos de intenção ordenados por rank."""
        return (
            self.db.query(IntentSummary)
            .filter(IntentSummary.analysis_id == analysis_id)
            .order_by(IntentSummary.rank.asc().nullslast())
            .all()
        )

    def get_posts_by_intent(
        self,
        analysis_id: UUID,
        intent_category: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[PostIntentClassification]:
        """Retorna posts paginados filtrados por categoria de intenção."""
        return (
            self.db.query(PostIntentClassification)
            .filter(
                PostIntentClassification.analysis_id == analysis_id,
                or_(
                    PostIntentClassification.primary_intent == intent_category,
                    PostIntentClassification.secondary_intent == intent_category,
                ),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count_posts_by_intent(self, analysis_id: UUID, intent_category: str) -> int:
        """Conta posts para uma categoria de intenção."""
        return (
            self.db.query(PostIntentClassification)
            .filter(
                PostIntentClassification.analysis_id == analysis_id,
                or_(
                    PostIntentClassification.primary_intent == intent_category,
                    PostIntentClassification.secondary_intent == intent_category,
                ),
            )
            .count()
        )

    def delete_old_analyses(
        self, audience_id: UUID, window: str, keep_latest: int = 2
    ) -> int:
        """Remove classificações antigas, mantendo as N mais recentes."""
        latest_ids = (
            self.db.query(IntentClassificationAnalysis.id)
            .filter(
                IntentClassificationAnalysis.audience_id == audience_id,
                IntentClassificationAnalysis.time_window == window,
            )
            .order_by(IntentClassificationAnalysis.created_at.desc())
            .limit(keep_latest)
            .all()
        )
        keep_ids = [row[0] for row in latest_ids]

        if not keep_ids:
            return 0

        deleted = (
            self.db.query(IntentClassificationAnalysis)
            .filter(
                IntentClassificationAnalysis.audience_id == audience_id,
                IntentClassificationAnalysis.time_window == window,
                IntentClassificationAnalysis.id.notin_(keep_ids),
            )
            .delete(synchronize_session="fetch")
        )
        self.db.commit()
        return deleted
