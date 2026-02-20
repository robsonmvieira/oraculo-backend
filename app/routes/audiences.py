"""Routes for audiences management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.modules.identity.dependencies import get_current_user
from app.modules.identity.domain.entities.user import User
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
from app.modules.shared.infra.database.database import get_db

router = APIRouter(prefix="/audiences", tags=["Audiences"])


class CreateAudienceRequest(BaseModel):
    name: str
    description: str | None = None


class UpdateAudienceRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class AddCommunityRequest(BaseModel):
    subreddit_name: str


@router.get("")
def list_audiences(current_user: User = Depends(get_current_user), db=Depends(get_db)):
    """
    Lista todas as audiências com dados agregados para os cards.

    Returns:
        Lista de cards com: name, total_subs, total_members, growth_week, icons
    """
    use_case = ListAudienceCardsUseCase(db)
    cards = use_case.execute()
    return {"audiences": [vars(card) for card in cards]}


@router.post("")
def create_audience(request: CreateAudienceRequest, current_user: User = Depends(get_current_user), db=Depends(get_db)):
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


@router.get("/{audience_id}")
def get_audience_card(audience_id: UUID, current_user: User = Depends(get_current_user), db=Depends(get_db)):
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


@router.put("/{audience_id}")
def update_audience(
    audience_id: UUID, request: UpdateAudienceRequest, current_user: User = Depends(get_current_user), db=Depends(get_db)
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


@router.delete("/{audience_id}")
def delete_audience(audience_id: UUID, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    """
    Remove uma audiência.
    """
    use_case = DeleteAudienceUseCase(db)
    deleted = use_case.execute(audience_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Audience not found")
    return {"deleted": True}


@router.post("/{audience_id}/communities")
def add_community_to_audience(
    audience_id: UUID, request: AddCommunityRequest, current_user: User = Depends(get_current_user), db=Depends(get_db)
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


@router.delete("/{audience_id}/communities/{subreddit_name}")
def remove_community_from_audience(
    audience_id: UUID, subreddit_name: str, current_user: User = Depends(get_current_user), db=Depends(get_db)
):
    """
    Remove uma comunidade de uma audiência.
    """
    use_case = RemoveCommunityFromAudienceUseCase(db)
    removed = use_case.execute(audience_id, subreddit_name)
    if not removed:
        raise HTTPException(status_code=404, detail="Community not found in audience")
    return {"removed": True}
