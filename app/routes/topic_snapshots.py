"""Routes for topic growth history (snapshots)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.domain.entities.user import User
from app.modules.shared.infra.database.database import get_db
from app.modules.topic_snapshots.application.use_cases.get_growth_history_use_case import (
    GetGrowthHistoryUseCase,
)

router = APIRouter(prefix="/audiences", tags=["Topic Growth History"])

AUDIENCE_NOT_FOUND = "Audience not found"


def _check_ownership(audience, current_user: User) -> None:
    """Valida que o usuario e dono da audiencia ou superuser."""
    if current_user.is_superuser:
        return
    if audience.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso negado")


@router.get("/{audience_id}/topics/{topic_id}/growth-history")
def get_topic_growth_history(
    audience_id: UUID,
    topic_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Retorna historico de crescimento de um topico ao longo do tempo.
    Permite ao frontend plotar grafico de tendencia.
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    use_case = GetGrowthHistoryUseCase(db)
    result = use_case.execute(audience_id=audience_id, topic_id=topic_id)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result
