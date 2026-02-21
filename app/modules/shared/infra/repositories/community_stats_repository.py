from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.modules.shared.domain.entities.community_stats import CommunityStats
from app.modules.shared.domain.value_objects.community_classification import (
    classify_activity,
    classify_size,
)


class CommunityStatsRepository:
    """
    Repositório para operações com community_stats.
    """

    def __init__(self, db: Session):
        self.db = db

    def find_by_name(self, subreddit_name: str) -> CommunityStats | None:
        """
        Busca estatísticas por nome do subreddit.

        Args:
            subreddit_name: Nome do subreddit

        Returns:
            CommunityStats ou None
        """
        return (
            self.db.query(CommunityStats)
            .filter(CommunityStats.subreddit_name == subreddit_name.lower())
            .first()
        )

    def find_by_names(self, subreddit_names: list[str]) -> list[CommunityStats]:
        """
        Busca estatísticas por múltiplos nomes.

        Args:
            subreddit_names: Lista de nomes

        Returns:
            Lista de CommunityStats
        """
        names_lower = [name.lower() for name in subreddit_names]
        return (
            self.db.query(CommunityStats)
            .filter(CommunityStats.subreddit_name.in_(names_lower))
            .all()
        )

    def upsert(
        self,
        subreddit_name: str,
        title: str | None = None,
        description: str | None = None,
        subscribers: int | None = None,
        icon_url: str | None = None,
        growth_week: float | None = None,
        growth_month: float | None = None,
        category: str | None = None,
    ) -> CommunityStats:
        """
        Insere ou atualiza estatísticas de uma comunidade.
        Recalcula size_tag e activity_tag automaticamente.

        Returns:
            CommunityStats atualizado/criado
        """
        existing = self.find_by_name(subreddit_name)

        if existing:
            self._apply_fields(existing, {
                "title": title,
                "description": description,
                "subscribers": subscribers,
                "icon_url": icon_url,
                "growth_week": growth_week,
                "growth_month": growth_month,
                "category": category,
            })
            existing.size_tag = classify_size(existing.subscribers)
            existing.activity_tag = classify_activity(existing.growth_week)
            existing.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        stats = CommunityStats(
            subreddit_name=subreddit_name.lower(),
            title=title,
            description=description,
            subscribers=subscribers,
            icon_url=icon_url,
            growth_week=growth_week,
            growth_month=growth_month,
            category=category,
            size_tag=classify_size(subscribers),
            activity_tag=classify_activity(growth_week),
        )
        self.db.add(stats)
        self.db.commit()
        self.db.refresh(stats)
        return stats

    @staticmethod
    def _apply_fields(entity: CommunityStats, fields: dict) -> None:
        """Apply non-None field values to an existing entity."""
        for key, value in fields.items():
            if value is not None:
                setattr(entity, key, value)

    def find_all(self, limit: int = 100) -> list[CommunityStats]:
        """
        Busca todas as comunidades com estatísticas.

        Args:
            limit: Número máximo de resultados

        Returns:
            Lista de CommunityStats
        """
        return (
            self.db.query(CommunityStats)
            .order_by(CommunityStats.subscribers.desc().nullslast())
            .limit(limit)
            .all()
        )

    def find_top_growing(self, limit: int = 20) -> list[CommunityStats]:
        """
        Busca comunidades com maior crescimento semanal.

        Args:
            limit: Número máximo de resultados

        Returns:
            Lista de CommunityStats ordenada por growth_week DESC
        """
        return (
            self.db.query(CommunityStats)
            .filter(CommunityStats.growth_week.isnot(None))
            .order_by(CommunityStats.growth_week.desc())
            .limit(limit)
            .all()
        )

    def browse(
        self,
        sort: str = "subscribers",
        category: str | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[CommunityStats], int]:
        """
        Browse comunidades com filtros, ordenação e paginação.

        Returns:
            Tupla (resultados, total)
        """
        query = self.db.query(CommunityStats)

        if category:
            query = query.filter(CommunityStats.category == category)

        if search:
            search_term = f"%{search.lower()}%"
            query = query.filter(
                (CommunityStats.subreddit_name.ilike(search_term))
                | (CommunityStats.title.ilike(search_term))
            )

        total = query.count()

        sort_map = {
            "subscribers": CommunityStats.subscribers.desc().nullslast(),
            "growth_week": CommunityStats.growth_week.desc().nullslast(),
            "growth_month": CommunityStats.growth_month.desc().nullslast(),
        }
        order = sort_map.get(sort, sort_map["subscribers"])
        query = query.order_by(order)

        results = query.offset(offset).limit(limit).all()

        return results, total

    def get_categories(self) -> list[str]:
        """Retorna categorias distintas existentes."""
        rows = (
            self.db.query(CommunityStats.category)
            .filter(CommunityStats.category.isnot(None))
            .distinct()
            .all()
        )
        return sorted([row[0] for row in rows])

    def find_uncategorized(self, limit: int = 100) -> list[CommunityStats]:
        """
        Busca comunidades sem categoria definida.

        Args:
            limit: Número máximo de resultados

        Returns:
            Lista de CommunityStats com category=NULL
        """
        return (
            self.db.query(CommunityStats)
            .filter(CommunityStats.category.is_(None))
            .order_by(CommunityStats.created_at.asc())
            .limit(limit)
            .all()
        )

    def find_oldest_updated(self, limit: int = 20) -> list[CommunityStats]:
        """
        Busca comunidades com updated_at mais antigo.
        Usado pelo script de expansão para processar rotativamente.
        """
        return (
            self.db.query(CommunityStats)
            .filter(CommunityStats.subscribers.isnot(None))
            .order_by(CommunityStats.updated_at.asc())
            .limit(limit)
            .all()
        )
