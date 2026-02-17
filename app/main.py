from fastapi import Depends, FastAPI

from app.modules.shared.infra.cache.redit_cache import RedisCache
from app.modules.shared.infra.database.database import get_db
from app.modules.topics.application.use_cases.general_use_case.general_use_case import (
    GeneralUseCase,
)
from app.modules.topics.application.use_cases.get_community_details_use_case.get_community_details_use_case import (
    GetCommunityDetailsUseCase,
)
from app.modules.topics.application.use_cases.get_related_communities_use_case.get_related_communities_use_case import (
    GetRelatedCommunitiesUseCase,
)
from app.modules.topics.application.use_cases.search_community_use_case.search_community_use_case import (
    SearchCommunityUseCase,
)
from app.modules.topics.infra.providers.reddit_provider.generic_reddit_provider import (
    GenericRedditProvider,
)
from app.modules.topics.infra.providers.reddit_provider.old_reddit_scraper import (
    OldRedditScraper,
)

app = FastAPI(
    title="CRM API",
    description="API para gerenciamento de leads e propostas",
    version="0.1.0",
)


@app.get("/")
def root():
    return {"message": "Hello from CRM!!!"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/topics")
def get_topics():
    """
    Lista os tópicos populares, trending e novos
    """
    reddit_provider = GenericRedditProvider()
    cache = RedisCache()
    general_use_case = GeneralUseCase(reddit_provider, cache)
    general_topics, trending_topics, new_topics = general_use_case.execute()
    return {
        "general_topics": general_topics,
        "trending_topics": trending_topics,
        "new_topics": new_topics,
    }


@app.get("/communities/search/{community_name}")
def search_community(community_name: str):
    """
    Busca uma comunidade pelo nome

    Args:
        community_name: Nome da comunidade a ser pesquisada

    Returns:
        Dados da comunidade encontrada
    """
    reddit_provider = GenericRedditProvider()
    cache = RedisCache()
    search_community_use_case = SearchCommunityUseCase(reddit_provider, cache)
    community = search_community_use_case.execute(community_name)
    return community


@app.get("/communities/{community_name}")
def get_community_details(community_name: str, db=Depends(get_db)):
    """
    Obtém os detalhes de uma comunidade

    Args:
        community_name: Nome da comunidade

    Returns:
        Detalhes da comunidade
    """
    reddit_provider = GenericRedditProvider()
    cache = RedisCache()
    use_case = GetCommunityDetailsUseCase(reddit_provider, cache, db)
    return use_case.execute(community_name)


@app.get("/communities/{community_name}/related")
def get_related_communities(community_name: str, limit: int = 10, db=Depends(get_db)):
    """
    Busca comunidades relacionadas a uma comunidade

    Args:
        community_name: Nome da comunidade de origem
        limit: Número máximo de comunidades relacionadas

    Returns:
        Lista de comunidades relacionadas
    """
    reddit_provider = GenericRedditProvider()
    scraper = OldRedditScraper()
    cache = RedisCache()
    use_case = GetRelatedCommunitiesUseCase(reddit_provider, scraper, cache, db)
    return use_case.execute(community_name, limit)
