from app.modules.shared.infra.cache.redit_cache import RedisCache
from app.modules.topics.infra.providers.reddit_provider.generic_reddit_provider import (
    GenericRedditProvider,
)


class SearchCommunityUseCase:
    """
    Search for a community by name
    """

    def __init__(
        self,
        reddit_provider: GenericRedditProvider,
        cache: RedisCache,
    ):
        """
        Inicializa o use case

        Args:
            reddit_provider: Provider para buscar dados do Reddit
            cache: Serviço de cache
        """
        self.reddit_provider = reddit_provider
        self.cache = cache

    def execute(self, community_name: str):
        """
        Executa o use case

        Args:
            community_name: Nome da comunidade a ser pesquisada

        Returns:
            Dados da comunidade encontrada
        """
        cache_key = f"community_search_{community_name}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data

        data = self.reddit_provider.search_community_by_name(community_name)
        self.cache.set(cache_key, data)
        return data
