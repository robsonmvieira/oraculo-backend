"""Routes for intent Q&A (single question about an intent category)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.domain.entities.user import User
from app.modules.intent_ask.application.use_cases.ask_intent_use_case.ask_intent_use_case import (
    AskIntentUseCase,
)
from app.modules.shared.infra.database.database import get_db

router = APIRouter(
    prefix="/audiences",
    tags=["Intent Ask"],
)

AUDIENCE_NOT_FOUND = "Audiência não encontrada"
VALID_WINDOWS = ("week", "month")
SUPPORTED_ASK_CATEGORIES = ("pain_and_anger", "solution_request")


class IntentAskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)


def _check_ownership(audience, current_user: User) -> None:
    """Valida que o usuario e dono da audiencia ou superuser."""
    if current_user.is_superuser:
        return
    if audience.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso negado")


@router.post("/{audience_id}/themes/intents/{category}/ask")
def ask_intent(
    audience_id: UUID,
    category: str,
    body: IntentAskRequest,
    window: str = Query("week", description="Janela temporal: week ou month"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Faz uma pergunta sobre uma categoria de intenção e recebe uma resposta baseada em IA.

    Usa os dados de classificação de intenção e análise de temas como contexto.
    Respostas são cacheadas por 48 horas.
    """
    if window not in VALID_WINDOWS:
        raise HTTPException(
            status_code=400,
            detail=f"Janela inválida. Use: {', '.join(VALID_WINDOWS)}",
        )

    if category not in SUPPORTED_ASK_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Q&A não disponível para a categoria '{category}'. "
            f"Categorias suportadas: {', '.join(SUPPORTED_ASK_CATEGORIES)}",
        )

    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    use_case = AskIntentUseCase(db)
    result = use_case.execute(
        audience_id=audience_id,
        user_id=current_user.id,
        intent_category=category,
        question=body.question,
        window=window,
        language=current_user.preferred_language,
    )

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result
