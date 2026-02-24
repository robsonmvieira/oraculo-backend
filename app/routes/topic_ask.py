"""Routes for topic Q&A (Ask)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.modules.audience_topics.infra.repositories.audience_topic_repository import (
    AudienceTopicRepository,
)
from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.domain.entities.user import User
from app.modules.shared.infra.database.database import get_db
from app.modules.topic_ask.application.use_cases.ask_topic_use_case.ask_topic_use_case import (
    AskTopicUseCase,
)

router = APIRouter(prefix="/audiences", tags=["Topic Ask"])

AUDIENCE_NOT_FOUND = "Audience not found"
TOPIC_NOT_FOUND = "Topic not found"


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)


def _check_ownership(audience, current_user: User) -> None:
    """Valida que o usuário é dono da audiência ou superuser."""
    if current_user.is_superuser:
        return
    if audience.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso negado")


@router.post("/{audience_id}/topics/{topic_id}/ask")
def ask_topic(
    audience_id: UUID,
    topic_id: UUID,
    body: AskRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Faz uma pergunta sobre um tópico e recebe uma resposta baseada em IA.

    Usa os dados do Deep Dive (se disponível) como contexto para responder.
    Respostas são cacheadas por 48 horas.
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    topic_repo = AudienceTopicRepository(db)
    topic = topic_repo.get_topic_by_id(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail=TOPIC_NOT_FOUND)

    use_case = AskTopicUseCase(db)
    result = use_case.execute(
        topic_id=topic_id,
        audience_id=audience_id,
        user_id=current_user.id,
        question=body.question,
        language=current_user.preferred_language,
    )

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result
