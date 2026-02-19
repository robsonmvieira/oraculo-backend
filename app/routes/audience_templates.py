"""Routes for audience templates."""

import threading
import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.modules.audience_templates.application.use_cases.generate_audience_template_use_case import (
    GenerateAudienceTemplateUseCase,
)
from app.modules.audience_templates.infra.repositories.audience_template_repository import (
    AudienceTemplateRepository,
)
from app.modules.shared.application.services.community_stats_service import (
    CommunityStatsService,
)
from app.modules.shared.infra.database.database import SessionLocal, get_db
from app.modules.shared.infra.repositories.community_stats_repository import (
    CommunityStatsRepository,
)
from app.modules.topics.infra.providers.reddit_provider.generic_reddit_provider import (
    GenericRedditProvider,
)

router = APIRouter(prefix="/audience-templates", tags=["Audience Templates"])


class GenerateTemplateRequest(BaseModel):
    """Request body for generating a template."""

    name: str
    description: str | None = None
    icon: str | None = None
    category: str | None = None
    max_subreddits: int = 15


@router.get("")
def list_audience_templates(
    category: str | None = None,
    active_only: bool = True,
    db=Depends(get_db),
):
    """
    Lista todos os templates de audiência disponíveis.

    Args:
        category: Filtrar por categoria (business, lifestyle, tech)
        active_only: Apenas templates ativos (default: True)

    Returns:
        Lista de templates com suas comunidades
    """
    repository = AudienceTemplateRepository(db)
    stats_repo = CommunityStatsRepository(db)
    templates = repository.find_all(active_only=active_only, category=category)

    result = []
    for template in templates:
        communities = repository.get_communities(template.id)
        community_names = [c.subreddit_name for c in communities]

        total_subscribers = 0
        subscribers_loaded = 0
        for name in community_names:
            cached = stats_repo.find_by_name(name)
            if cached and cached.subscribers is not None:
                total_subscribers += cached.subscribers
                subscribers_loaded += 1

        result.append(
            {
                "id": str(template.id),
                "name": template.name,
                "slug": template.slug,
                "description": template.description,
                "icon": template.icon,
                "category": template.category,
                "display_order": template.display_order,
                "communities": community_names,
                "communities_count": len(communities),
                "total_subscribers": total_subscribers,
                "subscribers_loaded": subscribers_loaded,
            }
        )

    return {"templates": result}


@router.get("/{template_id}")
def get_audience_template(template_id: UUID, db=Depends(get_db)):
    """
    Retorna detalhes de um template de audiência com dados enriquecidos.

    Para cada comunidade, busca:
    - subscribers, title, icon_url do Reddit
    - growth_week, growth_month do SubredditStats

    Se os dados não estiverem em cache, dispara job em background.
    """
    repository = AudienceTemplateRepository(db)
    template = repository.find_by_id(template_id)

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    communities = repository.get_communities(template.id)
    community_names = [c.subreddit_name for c in communities]

    # Buscar dados enriquecidos do cache (community_stats)
    enriched_communities = []
    communities_to_fetch = []

    stats_repo = CommunityStatsRepository(db)

    for name in community_names:
        cached = stats_repo.find_by_name(name)

        if cached and cached.is_cache_valid(24):
            enriched_communities.append(
                {
                    "name": name,
                    "title": cached.title,
                    "subscribers": cached.subscribers,
                    "icon_url": cached.icon_url,
                    "growth_week": cached.growth_week,
                    "growth_month": cached.growth_month,
                }
            )
        else:
            # Dados não estão em cache, adicionar para buscar em background
            communities_to_fetch.append(name)
            enriched_communities.append(
                {
                    "name": name,
                    "title": None,
                    "subscribers": None,
                    "icon_url": None,
                    "growth_week": None,
                    "growth_month": None,
                }
            )

    # Se há comunidades sem cache, disparar job em background
    if communities_to_fetch:
        _fetch_community_stats_in_background(communities_to_fetch)

    # Calcular total de subscribers das comunidades com dados carregados
    subscribers_with_data = [
        c["subscribers"] for c in enriched_communities if c["subscribers"] is not None
    ]
    total_subscribers = sum(subscribers_with_data)
    subscribers_loaded = len(subscribers_with_data)

    return {
        "id": str(template.id),
        "name": template.name,
        "slug": template.slug,
        "description": template.description,
        "icon": template.icon,
        "category": template.category,
        "display_order": template.display_order,
        "communities": enriched_communities,
        "communities_count": len(communities),
        "communities_loading": len(communities_to_fetch),
        "total_subscribers": total_subscribers,
        "subscribers_loaded": subscribers_loaded,
    }


def _fetch_community_stats_in_background(community_names: list[str]) -> None:
    """
    Busca dados de comunidades em background.
    Respeita rate limit com delay entre requests.
    """

    def background_task():
        db = SessionLocal()
        try:
            stats_service = CommunityStatsService(db)
            reddit_provider = GenericRedditProvider()

            for name in community_names:
                try:
                    # Buscar dados do Reddit
                    reddit_data = reddit_provider.get_community_details(name)
                    # Buscar/atualizar stats (inclui growth do SubredditStats)
                    stats_service.get_stats(name, reddit_data)
                    # Delay para respeitar rate limit
                    time.sleep(1)
                except Exception:
                    continue
        finally:
            db.close()

    thread = threading.Thread(target=background_task, daemon=True)
    thread.start()


@router.post("/generate")
def generate_audience_template(request: GenerateTemplateRequest, db=Depends(get_db)):
    """
    Gera um template de audiência usando LLM + Reddit search.

    O LLM:
    1. Gera keywords de busca baseado no nome
    2. Busca subreddits relevantes no Reddit
    3. Filtra e valida os melhores subreddits

    Args:
        request: Nome, descrição, ícone, categoria e max_subreddits

    Returns:
        Template gerado com subreddits encontrados
    """
    use_case = GenerateAudienceTemplateUseCase(db)
    result = use_case.execute(
        audience_name=request.name,
        description=request.description,
        icon=request.icon,
        category=request.category,
        max_subreddits=request.max_subreddits,
    )

    return {
        "template": {
            "id": str(result.template.id),
            "name": result.template.name,
            "slug": result.template.slug,
            "description": result.template.description,
            "icon": result.template.icon,
            "category": result.template.category,
        },
        "subreddits_found": [
            {
                "name": s.name,
                "title": s.title,
                "subscribers": s.subscribers,
            }
            for s in result.subreddits_found
        ],
        "subreddits_added": result.subreddits_added,
    }
