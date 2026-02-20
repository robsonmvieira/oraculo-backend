from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.modules.shared.domain.entities.community_stats import CommunityStats
from app.modules.shared.infra.repositories.community_stats_repository import (
    CommunityStatsRepository,
)
from app.modules.topics.infra.providers.subreddit_stats_provider.subreddit_stats_provider import (
    SubredditStatsProvider,
)


@dataclass
class CommunityStatsDTO:
    """DTO com estatísticas de uma comunidade."""

    subreddit_name: str
    title: str | None = None
    description: str | None = None
    subscribers: int | None = None
    icon_url: str | None = None
    growth_week: float | None = None
    growth_month: float | None = None
    category: str | None = None

    @classmethod
    def from_entity(cls, entity: CommunityStats) -> "CommunityStatsDTO":
        return cls(
            subreddit_name=entity.subreddit_name,
            title=entity.title,
            description=entity.description,
            subscribers=entity.subscribers,
            icon_url=entity.icon_url,
            growth_week=entity.growth_week,
            growth_month=entity.growth_month,
            category=entity.category,
        )


class CommunityStatsService:
    """
    Serviço para buscar estatísticas de comunidades.
    Implementa cache híbrido: banco de dados + API externa.
    """

    CACHE_MAX_AGE_HOURS = 24

    def __init__(self, db: Session):
        self.repository = CommunityStatsRepository(db)
        self.stats_provider = SubredditStatsProvider()

    def get_stats(
        self,
        subreddit_name: str,
        reddit_data: dict | None = None,
        category: str | None = None,
    ) -> CommunityStatsDTO | None:
        """
        Busca estatísticas de uma comunidade.
        1. Verifica cache no banco
        2. Se expirado, busca na API externa
        3. Salva no banco

        Args:
            subreddit_name: Nome do subreddit
            reddit_data: Dados já obtidos do Reddit API (opcional)

        Returns:
            CommunityStatsDTO ou None
        """
        # 1. Verificar cache
        cached = self.repository.find_by_name(subreddit_name)
        if cached and cached.is_cache_valid(self.CACHE_MAX_AGE_HOURS):
            return CommunityStatsDTO.from_entity(cached)

        # 2. Buscar dados de crescimento na API externa
        growth_data = self.stats_provider.get_growth_data(subreddit_name)

        # 3. Extrair dados do Reddit (se fornecido)
        title = None
        description = None
        subscribers = None
        icon_url = None

        if reddit_data:
            data = reddit_data.get("data", reddit_data)
            title = data.get("title")
            description = data.get("public_description")
            subscribers = data.get("subscribers")
            icon_url = data.get("community_icon") or data.get("icon_img")
            # Limpar URL (remove &amp; encoding)
            if icon_url:
                icon_url = icon_url.replace("&amp;", "&")

        # 4. Se NÃO temos subscribers do Reddit, usar da growth_data como fallback
        if not subscribers and growth_data and growth_data.subscribers:
            subscribers = growth_data.subscribers

        # 5. Salvar no banco
        stats = self.repository.upsert(
            subreddit_name=subreddit_name,
            title=title,
            description=description,
            subscribers=subscribers,
            icon_url=icon_url,
            growth_week=growth_data.growth_week if growth_data else None,
            growth_month=growth_data.growth_month if growth_data else None,
            category=category,
        )

        return CommunityStatsDTO.from_entity(stats)

    def get_stats_batch(
        self,
        subreddit_names: list[str],
        reddit_data_map: dict[str, dict] | None = None,
    ) -> dict[str, CommunityStatsDTO]:
        """
        Busca estatísticas de múltiplas comunidades.

        Args:
            subreddit_names: Lista de nomes
            reddit_data_map: Mapa {nome: dados do Reddit} (opcional)

        Returns:
            Dicionário {nome: CommunityStatsDTO}
        """
        results = {}
        reddit_data_map = reddit_data_map or {}

        for name in subreddit_names:
            stats = self.get_stats(
                subreddit_name=name,
                reddit_data=reddit_data_map.get(name.lower()),
            )
            if stats:
                results[name.lower()] = stats

        return results

    def get_top_growing(self, limit: int = 20) -> list[CommunityStatsDTO]:
        """
        Busca comunidades com maior crescimento semanal (do cache).

        Args:
            limit: Número máximo de resultados

        Returns:
            Lista de CommunityStatsDTO ordenada por crescimento
        """
        entities = self.repository.find_top_growing(limit)
        return [CommunityStatsDTO.from_entity(e) for e in entities]
