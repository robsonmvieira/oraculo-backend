"""Routes for community browsing (hybrid: local DB + Reddit fallback)."""

from fastapi import APIRouter, Depends, Query

from app.modules.shared.infra.cache.redit_cache import RedisCache
from app.modules.shared.infra.database.database import get_db
from app.modules.shared.infra.repositories.community_stats_repository import (
    CommunityStatsRepository,
)
from app.modules.topics.application.use_cases.browse_communities_use_case import (
    BrowseCommunitiesUseCase,
)
from app.modules.topics.infra.providers.reddit_provider.generic_reddit_provider import (
    GenericRedditProvider,
)

router = APIRouter(tags=["Communities"])


@router.get("/communities/browse")
def browse_communities(
    sort: str = Query(
        default="subscribers",
        pattern="^(subscribers|growth_week|growth_month)$",
    ),
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db),
):
    """
    Browse comunidades com busca híbrida.

    Consulta local (community_stats) e, quando o parâmetro search é
    fornecido e os resultados locais são poucos, faz fallback para a
    Reddit API, salva os resultados e retorna a lista combinada.
    """
    reddit_provider = GenericRedditProvider()
    cache = RedisCache()
    use_case = BrowseCommunitiesUseCase(reddit_provider, cache, db)
    return use_case.execute(
        sort=sort,
        category=category,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/communities/categories")
def list_categories(db=Depends(get_db)):
    """Retorna categorias distintas existentes na base."""
    repo = CommunityStatsRepository(db)
    categories = repo.get_categories()
    return {"categories": categories}
