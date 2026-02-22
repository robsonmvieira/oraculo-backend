"""Routes for cross-topic pattern detection (Patterns)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.modules.topic_patterns.application.use_cases.trigger_pattern_analysis_use_case import (
    TriggerPatternAnalysisUseCase,
)
from app.modules.topic_patterns.infra.repositories.topic_pattern_repository import (
    TopicPatternRepository,
)
from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.domain.entities.user import User
from app.modules.shared.infra.database.database import get_db

router = APIRouter(prefix="/audiences", tags=["Topic Patterns"])

AUDIENCE_NOT_FOUND = "Audience not found"


def _check_ownership(audience, current_user: User) -> None:
    """Valida que o usuario e dono da audiencia ou superuser."""
    if current_user.is_superuser:
        return
    if audience.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso negado")


@router.get("/{audience_id}/topics/patterns")
def get_topic_patterns(
    audience_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Retorna a analise de padroes cross-topic da audiencia.

    Se nao existe analise, retorna status 'no_analysis'.
    Se esta em processamento, retorna status 'processing'.
    Se esta pronta, retorna os dados completos.
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    pattern_repo = TopicPatternRepository(db)
    latest = pattern_repo.find_latest_by_audience(audience_id)

    if not latest:
        return {
            "status": "no_analysis",
            "message": "Nenhuma analise de padroes encontrada. Clique em 'Patterns' para iniciar.",
            "audience_id": str(audience_id),
        }

    if latest.status == "processing":
        return {
            "status": "processing",
            "message": "Analise de padroes em andamento. Tente novamente em alguns minutos.",
            "analysis_id": str(latest.id),
            "audience_id": str(audience_id),
        }

    if latest.status == "failed":
        return {
            "status": "failed",
            "message": f"Analise falhou: {latest.error_message or 'erro desconhecido'}",
            "analysis_id": str(latest.id),
            "audience_id": str(audience_id),
        }

    # Status ready — buscar padroes
    pattern = pattern_repo.get_pattern(latest.id)
    if not pattern:
        return {
            "status": "failed",
            "message": "Analise marcada como pronta mas sem dados.",
            "analysis_id": str(latest.id),
            "audience_id": str(audience_id),
        }

    return {
        "status": "ready",
        "analysis_id": str(latest.id),
        "audience_id": str(audience_id),
        "completed_at": latest.completed_at.isoformat() if latest.completed_at else None,
        "summary": pattern.summary,
        "co_occurrences": pattern.co_occurrences,
        "unanswered_questions": pattern.unanswered_questions,
        "emerging_opinions": pattern.emerging_opinions,
        "cross_community_gaps": pattern.cross_community_gaps,
        "content_opportunities": pattern.content_opportunities,
    }


@router.post("/{audience_id}/topics/patterns/refresh", status_code=202)
def refresh_topic_patterns(
    audience_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Forca reprocessamento da analise de padroes cross-topic.
    Util quando o usuario quer dados atualizados.
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    # Verificar se ja ha uma analise em processamento
    pattern_repo = TopicPatternRepository(db)
    latest = pattern_repo.find_latest_by_audience(audience_id)
    if latest and latest.status == "processing":
        return {
            "status": "processing",
            "message": "Ja existe uma analise em andamento.",
            "analysis_id": str(latest.id),
        }

    trigger = TriggerPatternAnalysisUseCase(db)
    result = trigger.execute(audience_id, force=True, language=current_user.preferred_language)

    return result
