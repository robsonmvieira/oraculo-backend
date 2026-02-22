"""Routes for audience topic analysis."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.modules.audience_topics.application.use_cases.trigger_topic_analysis_use_case import (
    TriggerTopicAnalysisUseCase,
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

router = APIRouter(prefix="/audiences", tags=["Audience Topics"])

AUDIENCE_NOT_FOUND = "Audience not found"


def _check_ownership(audience, current_user: User) -> None:
    """Valida que o usuário é dono da audiência ou superuser."""
    if current_user.is_superuser:
        return
    if audience.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso negado")


@router.get("/{audience_id}/topics")
def list_audience_topics(
    audience_id: UUID,
    sort_by: str = "rank",
    limit: int = 200,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Lista tópicos extraídos de uma audiência.

    Retorna a análise mais recente com status 'ready'.
    Se não existe ou está em processamento, retorna status correspondente.

    sort_by: rank (padrão), growth, frequency, name
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    topic_repo = AudienceTopicRepository(db)

    # Buscar análise mais recente (qualquer status)
    latest = topic_repo.find_latest_by_audience(audience_id)

    if not latest:
        return {
            "status": "no_analysis",
            "message": "Nenhuma análise de tópicos encontrada. Adicione comunidades à audiência.",
            "topics": [],
            "total_topics": 0,
        }

    if latest.status == "processing":
        return {
            "status": "processing",
            "message": "Análise de tópicos em andamento. Tente novamente em alguns minutos.",
            "topics": [],
            "total_topics": 0,
        }

    if latest.status == "failed":
        return {
            "status": "failed",
            "message": f"Análise falhou: {latest.error_message or 'erro desconhecido'}",
            "topics": [],
            "total_topics": 0,
        }

    # Status ready — buscar tópicos
    topics = topic_repo.get_topics(
        analysis_id=latest.id,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )

    return {
        "status": "ready",
        "analysis_id": str(latest.id),
        "total_topics": latest.total_topics,
        "completed_at": latest.completed_at.isoformat() if latest.completed_at else None,
        "topics": [
            {
                "id": str(t.id),
                "name": t.name,
                "description": t.description,
                "growth_percentage": t.growth_percentage,
                "mention_frequency": t.mention_frequency,
                "mention_period": t.mention_period,
                "post_count": t.post_count,
                "communities": t.communities,
                "rank": t.rank,
            }
            for t in topics
        ],
    }


@router.get("/{audience_id}/topics/{topic_id}")
def get_audience_topic_detail(
    audience_id: UUID,
    topic_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Retorna detalhe completo de um tópico específico.
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    topic_repo = AudienceTopicRepository(db)
    topic = topic_repo.get_topic_by_id(topic_id)

    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    return {
        "id": str(topic.id),
        "name": topic.name,
        "description": topic.description,
        "growth_percentage": topic.growth_percentage,
        "mention_frequency": topic.mention_frequency,
        "mention_period": topic.mention_period,
        "post_count": topic.post_count,
        "communities": topic.communities,
        "rank": topic.rank,
        "created_at": topic.created_at.isoformat() if topic.created_at else None,
    }


@router.post("/{audience_id}/topics/refresh", status_code=202)
def refresh_audience_topics(
    audience_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Força reprocessamento da análise de tópicos.
    Útil quando o usuário quer dados atualizados.
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    communities = audience_repo.get_communities(audience_id)
    if not communities:
        raise HTTPException(
            status_code=400,
            detail="Audiência não possui comunidades para análise",
        )

    topic_repo = AudienceTopicRepository(db)

    # Verificar se já há uma análise em processamento
    latest = topic_repo.find_latest_by_audience(audience_id)
    if latest and latest.status == "processing":
        return {
            "status": "processing",
            "message": "Já existe uma análise em andamento.",
        }

    # Criar nova análise (ignora fingerprint — força reprocessamento)
    community_names = [c.subreddit_name for c in communities]
    fingerprint = AudienceTopicRepository.generate_fingerprint(community_names)
    analysis = topic_repo.create_analysis(audience_id, fingerprint)

    trigger = TriggerTopicAnalysisUseCase(db)
    trigger._run_in_background(audience_id, analysis.id, language=current_user.preferred_language)

    return {
        "status": "processing",
        "message": "Análise de tópicos iniciada. Consulte novamente em alguns minutos.",
        "analysis_id": str(analysis.id),
    }
