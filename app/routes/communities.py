"""Routes for community browsing (local DB only)."""

from fastapi import APIRouter, Depends, Query

from app.modules.shared.infra.database.database import get_db
from app.modules.shared.infra.repositories.community_stats_repository import (
    CommunityStatsRepository,
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
    Browse comunidades pré-populadas.

    Consulta local (community_stats), sem chamadas externas.
    Ideal para o modal de "Nova Audiência".
    """
    repo = CommunityStatsRepository(db)
    results, total = repo.browse(
        sort=sort,
        category=category,
        search=search,
        limit=limit,
        offset=offset,
    )

    return {
        "communities": [
            {
                "name": c.subreddit_name,
                "title": c.title,
                "description": c.description,
                "subscribers": c.subscribers,
                "icon_url": c.icon_url,
                "growth_week": c.growth_week,
                "growth_month": c.growth_month,
                "category": c.category,
            }
            for c in results
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total,
    }


@router.get("/communities/categories")
def list_categories(db=Depends(get_db)):
    """Retorna categorias distintas existentes na base."""
    repo = CommunityStatsRepository(db)
    categories = repo.get_categories()
    return {"categories": categories}
