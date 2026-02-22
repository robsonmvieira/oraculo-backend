"""Routes for topic deep dive analysis (Browse All)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.modules.topic_deep_dive.application.use_cases.trigger_deep_dive_use_case import (
    TriggerDeepDiveUseCase,
)
from app.modules.topic_deep_dive.infra.repositories.topic_deep_dive_repository import (
    TopicDeepDiveRepository,
)
from app.modules.audience_topics.infra.repositories.audience_topic_repository import (
    AudienceTopicRepository,
)
from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.domain.entities.user import User
from app.modules.shared.infra.database.database import get_db

router = APIRouter(prefix="/audiences", tags=["Topic Deep Dive"])

AUDIENCE_NOT_FOUND = "Audience not found"
TOPIC_NOT_FOUND = "Topic not found"


def _check_ownership(audience, current_user: User) -> None:
    """Valida que o usuário é dono da audiência ou superuser."""
    if current_user.is_superuser:
        return
    if audience.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso negado")


@router.get("/{audience_id}/topics/{topic_id}/deep-dive")
def get_topic_deep_dive(
    audience_id: UUID,
    topic_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Retorna a análise de deep dive de um tópico.

    Se não existe análise, retorna status 'no_analysis'.
    Se está em processamento, retorna status 'processing'.
    Se está pronta, retorna os dados completos.
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    # Verificar se o tópico existe
    topic_repo = AudienceTopicRepository(db)
    topic = topic_repo.get_topic_by_id(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail=TOPIC_NOT_FOUND)

    deep_dive_repo = TopicDeepDiveRepository(db)
    latest = deep_dive_repo.find_latest_by_topic(topic_id)

    if not latest:
        return {
            "status": "no_analysis",
            "message": "Nenhuma análise de deep dive encontrada. Clique em 'Browse All' para iniciar.",
            "topic_id": str(topic_id),
            "topic_name": topic.name,
        }

    if latest.status == "processing":
        return {
            "status": "processing",
            "message": "Análise de deep dive em andamento. Tente novamente em alguns minutos.",
            "analysis_id": str(latest.id),
            "topic_id": str(topic_id),
            "topic_name": topic.name,
        }

    if latest.status == "failed":
        return {
            "status": "failed",
            "message": f"Análise falhou: {latest.error_message or 'erro desconhecido'}",
            "analysis_id": str(latest.id),
            "topic_id": str(topic_id),
            "topic_name": topic.name,
        }

    # Status ready — buscar deep dive
    deep_dive = deep_dive_repo.get_deep_dive(latest.id)
    if not deep_dive:
        return {
            "status": "failed",
            "message": "Análise marcada como pronta mas sem dados.",
            "analysis_id": str(latest.id),
            "topic_id": str(topic_id),
            "topic_name": topic.name,
        }

    return {
        "status": "ready",
        "analysis_id": str(latest.id),
        "topic_id": str(topic_id),
        "topic_name": topic.name,
        "completed_at": latest.completed_at.isoformat() if latest.completed_at else None,
        "summary": deep_dive.summary,
        "subtopics": deep_dive.subtopics,
        "common_questions": deep_dive.common_questions,
        "sentiment": deep_dive.sentiment,
        "mentioned_products": deep_dive.mentioned_products,
        "representative_posts": deep_dive.representative_posts,
        "actionable_insights": deep_dive.actionable_insights,
    }


@router.post("/{audience_id}/topics/{topic_id}/deep-dive/refresh", status_code=202)
def refresh_topic_deep_dive(
    audience_id: UUID,
    topic_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Força reprocessamento da análise de deep dive.
    Útil quando o usuário quer dados atualizados.
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    # Verificar se o tópico existe
    topic_repo = AudienceTopicRepository(db)
    topic = topic_repo.get_topic_by_id(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail=TOPIC_NOT_FOUND)

    # Verificar se já há uma análise em processamento
    deep_dive_repo = TopicDeepDiveRepository(db)
    latest = deep_dive_repo.find_latest_by_topic(topic_id)
    if latest and latest.status == "processing":
        return {
            "status": "processing",
            "message": "Já existe uma análise em andamento.",
            "analysis_id": str(latest.id),
        }

    trigger = TriggerDeepDiveUseCase(db)
    result = trigger.execute(topic_id, audience_id, force=True, language=current_user.preferred_language)

    return result
