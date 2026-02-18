from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
from app.modules.audience_templates.application.use_cases.generate_audience_template_use_case import (
    GenerateAudienceTemplateUseCase,
)
from app.modules.audience_templates.infra.repositories.audience_template_repository import (
    AudienceTemplateRepository,
)
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


# Pydantic models for request bodies
class CreateAudienceRequest(BaseModel):
    name: str
    description: str | None = None


class UpdateAudienceRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class AddCommunityRequest(BaseModel):
    subreddit_name: str


class GenerateTemplateRequest(BaseModel):
    name: str
    description: str | None = None
    icon: str | None = None
    category: str | None = None
    max_subreddits: int = 15


app = FastAPI(
    title="CRM API",
    description="API para gerenciamento de leads e propostas",
    version="0.1.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.get("/community-details/{community_name}")
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


# ==================== AUDIENCE TEMPLATES ====================


@app.get("/audience-templates")
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
    templates = repository.find_all(active_only=active_only, category=category)

    result = []
    for template in templates:
        communities = repository.get_communities(template.id)
        result.append(
            {
                "id": str(template.id),
                "name": template.name,
                "slug": template.slug,
                "description": template.description,
                "icon": template.icon,
                "category": template.category,
                "display_order": template.display_order,
                "communities": [c.subreddit_name for c in communities],
                "communities_count": len(communities),
            }
        )

    return {"templates": result}


@app.get("/audience-templates/{template_id}")
def get_audience_template(template_id: UUID, db=Depends(get_db)):
    """
    Retorna detalhes de um template de audiência.
    """
    repository = AudienceTemplateRepository(db)
    template = repository.find_by_id(template_id)

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    communities = repository.get_communities(template.id)

    return {
        "id": str(template.id),
        "name": template.name,
        "slug": template.slug,
        "description": template.description,
        "icon": template.icon,
        "category": template.category,
        "display_order": template.display_order,
        "communities": [c.subreddit_name for c in communities],
        "communities_count": len(communities),
    }


@app.post("/audience-templates/generate")
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
