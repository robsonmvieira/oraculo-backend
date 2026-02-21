import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audience_keywords.domain.entities.audience_keyword import (
    AudienceKeyword,
    AudienceKeywordAnalysis,
)


class AudienceKeywordRepository:
    """Repositório para operações com análises de keywords de audiências."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def generate_fingerprint(community_names: list[str]) -> str:
        """Gera fingerprint SHA256 das comunidades ordenadas."""
        sorted_names = sorted(n.lower() for n in community_names)
        content = ":".join(sorted_names)
        return hashlib.sha256(content.encode()).hexdigest()

    def find_latest_ready(self, audience_id: UUID) -> AudienceKeywordAnalysis | None:
        """Busca a análise mais recente com status 'ready'."""
        return (
            self.db.query(AudienceKeywordAnalysis)
            .filter(
                AudienceKeywordAnalysis.audience_id == audience_id,
                AudienceKeywordAnalysis.status == "ready",
            )
            .order_by(AudienceKeywordAnalysis.created_at.desc())
            .first()
        )

    def find_latest_by_audience(self, audience_id: UUID) -> AudienceKeywordAnalysis | None:
        """Busca a análise mais recente (qualquer status)."""
        return (
            self.db.query(AudienceKeywordAnalysis)
            .filter(AudienceKeywordAnalysis.audience_id == audience_id)
            .order_by(AudienceKeywordAnalysis.created_at.desc())
            .first()
        )

    def find_by_fingerprint(
        self, audience_id: UUID, fingerprint: str
    ) -> AudienceKeywordAnalysis | None:
        """Busca análise por fingerprint (mesma composição de comunidades)."""
        return (
            self.db.query(AudienceKeywordAnalysis)
            .filter(
                AudienceKeywordAnalysis.audience_id == audience_id,
                AudienceKeywordAnalysis.communities_fingerprint == fingerprint,
                AudienceKeywordAnalysis.status.in_(["ready", "processing"]),
            )
            .order_by(AudienceKeywordAnalysis.created_at.desc())
            .first()
        )

    def create_analysis(
        self, audience_id: UUID, fingerprint: str
    ) -> AudienceKeywordAnalysis:
        """Cria um novo registro de análise com status 'processing'."""
        analysis = AudienceKeywordAnalysis(
            audience_id=audience_id,
            communities_fingerprint=fingerprint,
            status="processing",
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def mark_ready(
        self, analysis_id: UUID, total_keywords: int
    ) -> AudienceKeywordAnalysis | None:
        """Marca análise como pronta."""
        analysis = (
            self.db.query(AudienceKeywordAnalysis)
            .filter(AudienceKeywordAnalysis.id == analysis_id)
            .first()
        )
        if not analysis:
            return None

        analysis.status = "ready"
        analysis.total_keywords = total_keywords
        analysis.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def mark_failed(
        self, analysis_id: UUID, error_message: str
    ) -> AudienceKeywordAnalysis | None:
        """Marca análise como falha."""
        analysis = (
            self.db.query(AudienceKeywordAnalysis)
            .filter(AudienceKeywordAnalysis.id == analysis_id)
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

    def save_keywords(
        self, analysis_id: UUID, keywords: list[dict]
    ) -> list[AudienceKeyword]:
        """Salva lista de keywords extraídas."""
        entities = []
        for kw_data in keywords:
            keyword = AudienceKeyword(
                analysis_id=analysis_id,
                keyword=kw_data["keyword"],
                category=kw_data.get("category"),
                relevance_score=kw_data.get("relevance_score"),
                rank=kw_data.get("rank"),
            )
            self.db.add(keyword)
            entities.append(keyword)

        self.db.commit()
        return entities

    def get_keywords(
        self,
        analysis_id: UUID,
        sort_by: str = "rank",
        limit: int = 50,
        offset: int = 0,
    ) -> list[AudienceKeyword]:
        """Lista keywords de uma análise com ordenação."""
        query = self.db.query(AudienceKeyword).filter(
            AudienceKeyword.analysis_id == analysis_id
        )

        if sort_by == "relevance":
            query = query.order_by(AudienceKeyword.relevance_score.desc().nullslast())
        elif sort_by == "keyword":
            query = query.order_by(AudienceKeyword.keyword.asc())
        elif sort_by == "category":
            query = query.order_by(AudienceKeyword.category.asc().nullslast())
        else:
            query = query.order_by(AudienceKeyword.rank.asc().nullslast())

        return query.offset(offset).limit(limit).all()

    def delete_old_analyses(self, audience_id: UUID, keep_latest: int = 2) -> int:
        """Remove análises antigas, mantendo as N mais recentes."""
        latest_ids = (
            self.db.query(AudienceKeywordAnalysis.id)
            .filter(AudienceKeywordAnalysis.audience_id == audience_id)
            .order_by(AudienceKeywordAnalysis.created_at.desc())
            .limit(keep_latest)
            .all()
        )
        keep_ids = [row[0] for row in latest_ids]

        if not keep_ids:
            return 0

        deleted = (
            self.db.query(AudienceKeywordAnalysis)
            .filter(
                AudienceKeywordAnalysis.audience_id == audience_id,
                AudienceKeywordAnalysis.id.notin_(keep_ids),
            )
            .delete(synchronize_session="fetch")
        )
        self.db.commit()
        return deleted
