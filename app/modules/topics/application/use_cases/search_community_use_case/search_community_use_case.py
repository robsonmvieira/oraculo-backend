from sqlalchemy.orm import Session

from app.modules.shared.application.services.community_stats_service import (
    CommunityStatsService,
)
from app.modules.shared.infra.cache.redit_cache import RedisCache
from app.modules.topics.infra.providers.reddit_provider.generic_reddit_provider import (
    GenericRedditProvider,
)


class SearchCommunityUseCase:
    """
    Search for communities by name with growth data.
    """

    def __init__(
        self,
        reddit_provider: GenericRedditProvider,
        cache: RedisCache,
        db: Session | None = None,
    ):
        """
        Inicializa o use case.

        Args:
            reddit_provider: Provider para buscar dados do Reddit
            cache: Serviço de cache Redis
            db: Sessão do banco de dados (para buscar growth)
        """
        self.reddit_provider = reddit_provider
        self.cache = cache
        self.stats_service = CommunityStatsService(db) if db else None

    def execute(
        self,
        community_name: str,
        sort_by: str = "relevance",
        include_growth: bool = True,
    ) -> dict:
        """
        Executa a busca de comunidades.

        Args:
            community_name: Termo de busca
            sort_by: Ordenação - "relevance", "subscribers", "growth"
            include_growth: Se deve incluir dados de crescimento

        Returns:
            Dados das comunidades com growth_week e growth_month
        """
        # 1. Buscar comunidades no Reddit (com cache Redis)
        cache_key = f"community_search_{community_name}"
        cached_data = self.cache.get(cache_key)

        if cached_data:
            reddit_data = cached_data
        else:
            reddit_data = self.reddit_provider.search_community_by_name(community_name)
            self.cache.set(cache_key, reddit_data)

        # 2. Extrair lista de comunidades
        communities = reddit_data.get("data", {}).get("children", [])

        # 3. Enriquecer com dados de crescimento
        if include_growth and self.stats_service and communities:
            communities = self._enrich_with_growth(communities)

        # 4. Ordenar resultados
        if sort_by == "growth":
            communities = sorted(
                communities,
                key=lambda x: x.get("data", {}).get("growth_week") or 0,
                reverse=True,
            )
        elif sort_by == "subscribers":
            communities = sorted(
                communities,
                key=lambda x: x.get("data", {}).get("subscribers") or 0,
                reverse=True,
            )

        return {
            "kind": reddit_data.get("kind", "Listing"),
            "data": {
                "children": communities,
                "after": reddit_data.get("data", {}).get("after"),
                "before": reddit_data.get("data", {}).get("before"),
            },
        }

    def _enrich_with_growth(self, communities: list[dict]) -> list[dict]:
        """
        Enriquece lista de comunidades com dados de crescimento.

        Args:
            communities: Lista de comunidades do Reddit

        Returns:
            Lista enriquecida com growth_week e growth_month
        """
        for community in communities:
            data = community.get("data", {})
            subreddit_name = data.get("display_name")

            if not subreddit_name:
                continue

            # Buscar/atualizar stats (com cache no banco)
            stats = self.stats_service.get_stats(
                subreddit_name=subreddit_name,
                reddit_data=data,
            )

            if stats:
                data["growth_week"] = stats.growth_week
                data["growth_month"] = stats.growth_month
                # Atualizar icon_url se disponível no cache
                if stats.icon_url and not data.get("community_icon"):
                    data["community_icon"] = stats.icon_url

        return communities
