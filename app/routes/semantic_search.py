from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.identity.domain.entities.user import User
from app.modules.identity.infra.security import get_current_user
from app.modules.semantic_search.application.use_cases.semantic_search_use_case.semantic_search_use_case import (
    SemanticSearchUseCase,
)
from app.modules.shared.infra.database.database import get_db

router = APIRouter(prefix="/api/audiences", tags=["semantic-search"])

AUDIENCE_NOT_FOUND = "Audience not found"


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)


def _check_ownership(audience, current_user: User):
    if str(audience.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")


@router.post("/{audience_id}/semantic-search")
def semantic_search(
    audience_id: UUID,
    body: SemanticSearchRequest,
    limit: int = Query(50, ge=10, le=100, description="Max posts to analyze"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Busca semântica livre em todos os posts de uma audiência.
    Retorna resumo + posts agrupados por padrão temático.
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    use_case = SemanticSearchUseCase(db)
    result = use_case.execute(
        audience_id=audience_id,
        user_id=current_user.id,
        query=body.query,
        language=current_user.preferred_language or "en",
        limit=limit,
    )

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result
