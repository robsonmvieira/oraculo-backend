from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.modules.shared.domain.entities.community_stats import CommunityStats


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
    ) -> CommunityStats:
        """
        Insere ou atualiza estatísticas de uma comunidade.

        Args:
            subreddit_name: Nome do subreddit
            title: Título da comunidade
            description: Descrição
            subscribers: Número de inscritos
            icon_url: URL do ícone
            growth_week: Crescimento semanal em %
            growth_month: Crescimento mensal em %

        Returns:
            CommunityStats atualizado/criado
        """
        existing = self.find_by_name(subreddit_name)

        if existing:
            if title is not None:
                existing.title = title
            if description is not None:
                existing.description = description
            if subscribers is not None:
                existing.subscribers = subscribers
            if icon_url is not None:
                existing.icon_url = icon_url
            if growth_week is not None:
                existing.growth_week = growth_week
            if growth_month is not None:
                existing.growth_month = growth_month
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
        )
        self.db.add(stats)
        self.db.commit()
        self.db.refresh(stats)
        return stats

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
