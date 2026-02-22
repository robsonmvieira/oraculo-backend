"""Routes for per-topic behavioral pattern detection."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.modules.topic_behavioral_patterns.application.use_cases.trigger_behavioral_pattern_use_case import (
    TriggerBehavioralPatternUseCase,
)
from app.modules.topic_behavioral_patterns.infra.repositories.topic_behavioral_pattern_repository import (
    TopicBehavioralPatternRepository,
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

router = APIRouter(prefix="/audiences", tags=["Topic Behavioral Patterns"])

AUDIENCE_NOT_FOUND = "Audience not found"
TOPIC_NOT_FOUND = "Topic not found"


def _check_ownership(audience, current_user: User) -> None:
    """Valida que o usuário é dono da audiência ou superuser."""
    if current_user.is_superuser:
        return
    if audience.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso negado")


@router.get("/{audience_id}/topics/{topic_id}/behavioral-patterns")
def get_topic_behavioral_patterns(
    audience_id: UUID,
    topic_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Retorna a análise de padrões comportamentais de um tópico.

    Se não existe análise, retorna status 'no_analysis'.
    Se está em processamento, retorna status 'processing'.
    Se está pronta, retorna os dados completos.
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

    pattern_repo = TopicBehavioralPatternRepository(db)
    latest = pattern_repo.find_latest_by_topic(topic_id)

    if not latest:
        return {
            "status": "no_analysis",
            "message": "Nenhuma análise de padrões comportamentais encontrada. Clique em 'Patterns' para iniciar.",
            "topic_id": str(topic_id),
            "topic_name": topic.name,
        }

    if latest.status == "processing":
        return {
            "status": "processing",
            "message": "Análise de padrões comportamentais em andamento. Tente novamente em alguns minutos.",
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

    # Status ready — buscar padrões comportamentais
    pattern = pattern_repo.get_behavioral_pattern(latest.id)
    if not pattern:
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
        "summary": pattern.summary,
        "tool_patterns": pattern.tool_patterns,
        "workaround_patterns": pattern.workaround_patterns,
        "friction_patterns": pattern.friction_patterns,
        "shift_patterns": pattern.shift_patterns,
        "demand_signals": pattern.demand_signals,
    }


@router.post("/{audience_id}/topics/{topic_id}/behavioral-patterns/refresh", status_code=202)
def refresh_topic_behavioral_patterns(
    audience_id: UUID,
    topic_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Força reprocessamento da análise de padrões comportamentais.
    Útil quando o usuário quer dados atualizados.
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

    # Verificar se já há uma análise em processamento
    pattern_repo = TopicBehavioralPatternRepository(db)
    latest = pattern_repo.find_latest_by_topic(topic_id)
    if latest and latest.status == "processing":
        return {
            "status": "processing",
            "message": "Já existe uma análise em andamento.",
            "analysis_id": str(latest.id),
        }

    trigger = TriggerBehavioralPatternUseCase(db)
    result = trigger.execute(topic_id, audience_id, force=True)

    return result
