from app.modules.shared.infra.cache.redit_cache import RedisCache
from app.modules.topics.infra.providers.reddit_provider.generic_reddit_provider import (
    GenericRedditProvider,
)


class GeneralUseCase:
    """
    List general, trending and new topics
    """

    def __init__(
        self,
        reddit_provider: GenericRedditProvider,
        cache: RedisCache,
    ):
        """
        Inicializa o use case
        """
        self.reddit_provider = reddit_provider
        self.cache = cache

    def execute(self):
        """
        Executa o use case
        """
        general_topics = self._get_or_fetch(
            "popular_topics", self.reddit_provider.list_popular_topics
        )
        trending_topics = self._get_or_fetch(
            "trending_topics", self.reddit_provider.list_trending_topics
        )
        new_topics = self._get_or_fetch(
            "new_topics", self.reddit_provider.list_new_topics
        )

        return general_topics, trending_topics, new_topics

    def _get_or_fetch(self, cache_key: str, fetch_fn):
        """
        Busca no cache ou executa a função de fetch
        """
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data

        data = fetch_fn()
        self.cache.set(cache_key, data)
        return data
