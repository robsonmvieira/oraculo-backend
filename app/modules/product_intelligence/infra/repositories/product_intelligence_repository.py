"""Repositório para operações com análises de Product Intelligence."""

import hashlib
import logging
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.product_intelligence.domain.entities.product_intelligence import (
    ProductIntelligenceAnalysis,
    ProductOpportunity,
    ProductProfile,
)

logger = logging.getLogger(__name__)


class ProductIntelligenceRepository:
    """Repositório para operações com análises de Product Intelligence."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def generate_fingerprint(
        audience_id: UUID,
        community_names: list[str],
        window: str,
    ) -> str:
        """Gera fingerprint SHA256 incluindo período (semana ou mês ISO)."""
        today = date.today()
        if window == "week":
            period_key = f"{today.isocalendar().year}-W{today.isocalendar()[1]:02d}"
        elif window == "month":
            period_key = f"{today.year}-{today.month:02d}"
        else:
            period_key = str(today)

        sorted_names = sorted(n.lower() for n in community_names)
        raw = f"{audience_id}|{'|'.join(sorted_names)}|{window}|{period_key}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def find_latest_by_audience(
        self, audience_id: UUID
    ) -> ProductIntelligenceAnalysis | None:
        """Busca a análise mais recente para a audiência."""
        return (
            self.db.query(ProductIntelligenceAnalysis)
            .filter(ProductIntelligenceAnalysis.audience_id == audience_id)
            .order_by(ProductIntelligenceAnalysis.created_at.desc())
            .first()
        )

    def find_by_fingerprint(
        self, audience_id: UUID, fingerprint: str
    ) -> ProductIntelligenceAnalysis | None:
        """Busca análise por fingerprint (mesmo período e comunidades)."""
        return (
            self.db.query(ProductIntelligenceAnalysis)
            .filter(
                ProductIntelligenceAnalysis.audience_id == audience_id,
                ProductIntelligenceAnalysis.fingerprint == fingerprint,
                ProductIntelligenceAnalysis.status.in_(["ready", "processing"]),
            )
            .order_by(ProductIntelligenceAnalysis.created_at.desc())
            .first()
        )

    def create_analysis(
        self, audience_id: UUID, fingerprint: str
    ) -> ProductIntelligenceAnalysis:
        """Cria novo registro de análise com status 'processing'."""
        analysis = ProductIntelligenceAnalysis(
            audience_id=audience_id,
            fingerprint=fingerprint,
            status="processing",
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def mark_ready(
        self,
        analysis_id: UUID,
        total_products: int,
        total_mentions: int,
    ) -> ProductIntelligenceAnalysis | None:
        """Marca análise como pronta."""
        analysis = (
            self.db.query(ProductIntelligenceAnalysis)
            .filter(ProductIntelligenceAnalysis.id == analysis_id)
            .first()
        )
        if not analysis:
            return None

        analysis.status = "ready"
        analysis.total_products_found = total_products
        analysis.total_mentions_analyzed = total_mentions
        analysis.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def mark_failed(
        self, analysis_id: UUID, error_message: str
    ) -> ProductIntelligenceAnalysis | None:
        """Marca análise como falha."""
        analysis = (
            self.db.query(ProductIntelligenceAnalysis)
            .filter(ProductIntelligenceAnalysis.id == analysis_id)
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

    def save_product_profiles(self, analysis_id: UUID, profiles: list[dict]) -> int:
        """Salva lista de perfis de produtos extraídos."""
        for p in profiles:
            profile = ProductProfile(
                analysis_id=analysis_id,
                product_name=p["product_name"],
                normalized_name=p.get(
                    "normalized_name", p["product_name"].strip().lower()
                ),
                category=p.get("category", "tool"),
                total_mentions=p.get("total_mentions", 1),
                sentiment_score=p.get("sentiment_score"),
                sentiment_label=p.get("sentiment_label"),
                trend_direction=p.get("trend_direction"),
                positive_aspects=p.get("positive_aspects"),
                negative_aspects=p.get("negative_aspects"),
                gaps=p.get("gaps"),
                alternatives=p.get("alternatives"),
                evidence_quotes=p.get("evidence_quotes"),
                communities=p.get("communities"),
                use_cases=p.get("use_cases"),
            )
            self.db.add(profile)
        self.db.commit()
        return len(profiles)

    def save_product_opportunities(
        self, analysis_id: UUID, opportunities: list[dict]
    ) -> int:
        """Salva lista de oportunidades de mercado detectadas."""
        for o in opportunities:
            opp = ProductOpportunity(
                analysis_id=analysis_id,
                opportunity_type=o.get("opportunity_type", "unmet_demand"),
                title=o["title"],
                description=o.get("description"),
                opportunity_score=o.get("opportunity_score"),
                demand_signals=o.get("demand_signals"),
                existing_solutions_count=o.get("existing_solutions_count"),
                evidence=o.get("evidence"),
                related_products=o.get("related_products"),
            )
            self.db.add(opp)
        self.db.commit()
        return len(opportunities)

    def get_product_profiles(
        self,
        analysis_id: UUID,
        sort_by: str = "mentions",
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ProductProfile]:
        """Lista perfis de produtos de uma análise com ordenação e filtro."""
        query = self.db.query(ProductProfile).filter(
            ProductProfile.analysis_id == analysis_id
        )

        if category:
            query = query.filter(ProductProfile.category == category)

        if sort_by == "sentiment":
            query = query.order_by(ProductProfile.sentiment_score.desc().nullslast())
        elif sort_by == "name":
            query = query.order_by(ProductProfile.product_name.asc())
        else:
            query = query.order_by(ProductProfile.total_mentions.desc().nullslast())

        return query.offset(offset).limit(limit).all()

    def get_product_profile_by_id(self, product_id: UUID) -> ProductProfile | None:
        """Busca perfil de produto por ID."""
        return (
            self.db.query(ProductProfile)
            .filter(ProductProfile.id == product_id)
            .first()
        )

    def get_product_opportunities(self, analysis_id: UUID) -> list[ProductOpportunity]:
        """Lista oportunidades de uma análise ordenadas por score."""
        return (
            self.db.query(ProductOpportunity)
            .filter(ProductOpportunity.analysis_id == analysis_id)
            .order_by(ProductOpportunity.opportunity_score.desc().nullslast())
            .all()
        )

    def delete_old_analyses(self, audience_id: UUID, keep_latest: int = 2) -> int:
        """Remove análises antigas, mantendo as N mais recentes."""
        latest_ids = (
            self.db.query(ProductIntelligenceAnalysis.id)
            .filter(
                ProductIntelligenceAnalysis.audience_id == audience_id,
            )
            .order_by(ProductIntelligenceAnalysis.created_at.desc())
            .limit(keep_latest)
            .all()
        )
        keep_ids = [row[0] for row in latest_ids]

        if not keep_ids:
            return 0

        deleted = (
            self.db.query(ProductIntelligenceAnalysis)
            .filter(
                ProductIntelligenceAnalysis.audience_id == audience_id,
                ProductIntelligenceAnalysis.id.notin_(keep_ids),
            )
            .delete(synchronize_session="fetch")
        )
        self.db.commit()
        return deleted
