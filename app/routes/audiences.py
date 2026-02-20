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
from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.shared.infra.database.database import get_db

router = APIRouter(prefix="/audiences", tags=["Audiences"])

AUDIENCE_NOT_FOUND = "Audience not found"


class CreateAudienceRequest(BaseModel):
    name: str
    description: str | None = None
    subreddit_names: list[str] = []


class UpdateAudienceRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class AddCommunityRequest(BaseModel):
    subreddit_name: str


def _check_ownership(audience, current_user: User) -> None:
    """Valida que o usuário é dono da audiência ou superuser."""
    if current_user.is_superuser:
        return
    if audience.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso negado")


@router.get("")
def list_audiences(
    current_user: User = Depends(get_current_user), db=Depends(get_db)
):
    """
    Lista audiências do usuário autenticado.
    Superuser vê todas.
    """
    use_case = ListAudienceCardsUseCase(db)
    user_id = None if current_user.is_superuser else current_user.id
    cards = use_case.execute(user_id)
    return {"audiences": [vars(card) for card in cards]}


@router.post("", status_code=201)
def create_audience(
    request: CreateAudienceRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Cria uma nova audiência vinculada ao usuário autenticado.
    Aceita subreddit_names para vincular comunidades na criação.
    """
    use_case = CreateAudienceUseCase(db)
    input_data = CreateAudienceInput(
        name=request.name,
        description=request.description,
        user_id=current_user.id,
        subreddit_names=request.subreddit_names,
    )
    audience = use_case.execute(input_data)
    return vars(audience)


@router.get("/{audience_id}")
def get_audience_card(
    audience_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Retorna dados agregados de uma audiência para o card.
    """
    repository = AudienceRepository(db)
    audience = repository.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    use_case = GetAudienceCardUseCase(db)
    card = use_case.execute(audience_id)
    return vars(card)


@router.put("/{audience_id}")
def update_audience(
    audience_id: UUID,
    request: UpdateAudienceRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Atualiza uma audiência.
    """
    repository = AudienceRepository(db)
    audience = repository.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    use_case = UpdateAudienceUseCase(db)
    input_data = UpdateAudienceInput(
        name=request.name,
        description=request.description,
    )
    updated = use_case.execute(audience_id, input_data)
    return vars(updated)


@router.delete("/{audience_id}")
def delete_audience(
    audience_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Remove uma audiência.
    """
    repository = AudienceRepository(db)
    audience = repository.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    use_case = DeleteAudienceUseCase(db)
    use_case.execute(audience_id)
    return {"deleted": True}


@router.post("/{audience_id}/communities")
def add_community_to_audience(
    audience_id: UUID,
    request: AddCommunityRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Adiciona uma comunidade a uma audiência.
    """
    repository = AudienceRepository(db)
    audience = repository.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    use_case = AddCommunityToAudienceUseCase(db)
    added = use_case.execute(audience_id, request.subreddit_name)
    if not added:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)
    return {"added": True, "subreddit_name": request.subreddit_name}


@router.delete("/{audience_id}/communities/{subreddit_name}")
def remove_community_from_audience(
    audience_id: UUID,
    subreddit_name: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Remove uma comunidade de uma audiência.
    """
    repository = AudienceRepository(db)
    audience = repository.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    use_case = RemoveCommunityFromAudienceUseCase(db)
    removed = use_case.execute(audience_id, subreddit_name)
    if not removed:
        raise HTTPException(status_code=404, detail="Community not found in audience")
    return {"removed": True}
