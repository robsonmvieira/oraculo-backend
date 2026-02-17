from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from app.modules.audiences.application.use_cases.get_audience_card_use_case import (
    GetAudienceCardUseCase,
    ListAudienceCardsUseCase,
)
from app.modules.audiences.application.use_cases.manage_audience_use_case import (
    AddCommunityToAudienceUseCase,
    CreateAudienceInput,
    CreateAudienceUseCase,
    DeleteAudienceUseCase,
    RemoveCommunityFromAudienceUseCase,
    UpdateAudienceInput,
    UpdateAudienceUseCase,
)
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


# Pydantic models for request bodies
class CreateAudienceRequest(BaseModel):
    name: str
    description: str | None = None


class UpdateAudienceRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class AddCommunityRequest(BaseModel):
    subreddit_name: str

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


# ==================== AUDIENCES ====================


@app.get("/audiences")
def list_audiences(db=Depends(get_db)):
    """
    Lista todas as audiências com dados agregados para os cards.

    Returns:
        Lista de cards com: name, total_subs, total_members, growth_week, icons
    """
    use_case = ListAudienceCardsUseCase(db)
    cards = use_case.execute()
    return {"audiences": [vars(card) for card in cards]}


@app.post("/audiences")
def create_audience(request: CreateAudienceRequest, db=Depends(get_db)):
    """
    Cria uma nova audiência.

    Args:
        request: Nome e descrição da audiência

    Returns:
        Audiência criada
    """
    use_case = CreateAudienceUseCase(db)
    input_data = CreateAudienceInput(
        name=request.name,
        description=request.description,
    )
    audience = use_case.execute(input_data)
    return vars(audience)


@app.get("/audiences/{audience_id}")
def get_audience_card(audience_id: UUID, db=Depends(get_db)):
    """
    Retorna dados agregados de uma audiência para o card.

    Returns:
        Card com: name, total_subs, total_members, growth_week, growth_month, icons
    """
    use_case = GetAudienceCardUseCase(db)
    card = use_case.execute(audience_id)
    if not card:
        raise HTTPException(status_code=404, detail="Audience not found")
    return vars(card)


@app.put("/audiences/{audience_id}")
def update_audience(
    audience_id: UUID, request: UpdateAudienceRequest, db=Depends(get_db)
):
    """
    Atualiza uma audiência.
    """
    use_case = UpdateAudienceUseCase(db)
    input_data = UpdateAudienceInput(
        name=request.name,
        description=request.description,
    )
    audience = use_case.execute(audience_id, input_data)
    if not audience:
        raise HTTPException(status_code=404, detail="Audience not found")
    return vars(audience)


@app.delete("/audiences/{audience_id}")
def delete_audience(audience_id: UUID, db=Depends(get_db)):
    """
    Remove uma audiência.
    """
    use_case = DeleteAudienceUseCase(db)
    deleted = use_case.execute(audience_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Audience not found")
    return {"deleted": True}


@app.post("/audiences/{audience_id}/communities")
def add_community_to_audience(
    audience_id: UUID, request: AddCommunityRequest, db=Depends(get_db)
):
    """
    Adiciona uma comunidade a uma audiência.

    Args:
        audience_id: ID da audiência
        request: Nome do subreddit a adicionar
    """
    use_case = AddCommunityToAudienceUseCase(db)
    added = use_case.execute(audience_id, request.subreddit_name)
    if not added:
        raise HTTPException(status_code=404, detail="Audience not found")
    return {"added": True, "subreddit_name": request.subreddit_name}


@app.delete("/audiences/{audience_id}/communities/{subreddit_name}")
def remove_community_from_audience(
    audience_id: UUID, subreddit_name: str, db=Depends(get_db)
):
    """
    Remove uma comunidade de uma audiência.
    """
    use_case = RemoveCommunityFromAudienceUseCase(db)
    removed = use_case.execute(audience_id, subreddit_name)
    if not removed:
        raise HTTPException(status_code=404, detail="Community not found in audience")
    return {"removed": True}
