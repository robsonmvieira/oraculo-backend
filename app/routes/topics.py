"""Routes for topics and communities."""

from fastapi import APIRouter, Depends

from app.modules.shared.infra.cache.redit_cache import RedisCache
from app.modules.shared.infra.database.database import get_db
from app.modules.topics.application.use_cases.general_use_case.general_use_case import (
    GeneralUseCase,
)
from app.modules.topics.application.use_cases.get_community_details_use_case.get_community_details_use_case import (
    GetCommunityDetailsUseCase,
)
from app.modules.topics.application.use_cases.search_community_use_case.search_community_use_case import (
    SearchCommunityUseCase,
)
from app.modules.topics.infra.providers.reddit_provider.generic_reddit_provider import (
    GenericRedditProvider,
)

router = APIRouter(tags=["Topics"])


@router.get("/topics")
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


@router.get("/communities/search/{community_name}")
def search_community(
    community_name: str,
    sort_by: str = "relevance",
    include_growth: bool = True,
    db=Depends(get_db),
):
    """
    Busca comunidades pelo nome com dados de crescimento.

    Args:
        community_name: Termo de busca
        sort_by: Ordenação - "relevance", "subscribers", "growth"
        include_growth: Se deve incluir dados de crescimento (default: True)

    Returns:
        Lista de comunidades com growth_week e growth_month
    """
    reddit_provider = GenericRedditProvider()
    cache = RedisCache()
    search_community_use_case = SearchCommunityUseCase(reddit_provider, cache, db)
    return search_community_use_case.execute(
        community_name,
        sort_by=sort_by,
        include_growth=include_growth,
    )


@router.get("/community-details/{community_name}")
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
