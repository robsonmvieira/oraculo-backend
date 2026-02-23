"""Routes for topic sentiment analysis."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.modules.topic_sentiment.application.use_cases.trigger_sentiment_use_case import (
    TriggerSentimentUseCase,
)
from app.modules.topic_sentiment.infra.repositories.topic_sentiment_repository import (
    TopicSentimentRepository,
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

router = APIRouter(prefix="/audiences", tags=["Topic Sentiment"])

AUDIENCE_NOT_FOUND = "Audience not found"
TOPIC_NOT_FOUND = "Topic not found"


def _check_ownership(audience, current_user: User) -> None:
    """Valida que o usuário é dono da audiência ou superuser."""
    if current_user.is_superuser:
        return
    if audience.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso negado")


@router.get("/{audience_id}/topics/{topic_id}/sentiment")
def get_topic_sentiment(
    audience_id: UUID,
    topic_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Retorna a análise de sentimento de um tópico.

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

    sentiment_repo = TopicSentimentRepository(db)
    latest = sentiment_repo.find_latest_by_topic(topic_id)

    if not latest:
        return {
            "status": "no_analysis",
            "message": "Nenhuma análise de sentimento encontrada. Clique em 'Sentimento' para iniciar.",
            "topic_id": str(topic_id),
            "topic_name": topic.name,
        }

    if latest.status == "processing":
        return {
            "status": "processing",
            "message": "Análise de sentimento em andamento. Tente novamente em alguns minutos.",
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

    # Status ready — buscar sentimento
    sentiment = sentiment_repo.get_sentiment(latest.id)
    if not sentiment:
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
        "overall_sentiment": sentiment.overall_sentiment,
        "emotional_map": sentiment.emotional_map,
        "sentiment_by_community": sentiment.sentiment_by_community,
        "sentiment_by_subtopic": sentiment.sentiment_by_subtopic,
        "sentiment_drivers": sentiment.sentiment_drivers,
        "tension_points": sentiment.tension_points,
        "pain_points": sentiment.pain_points,
        "sentiment_opportunities": sentiment.sentiment_opportunities,
    }


@router.post("/{audience_id}/topics/{topic_id}/sentiment/refresh", status_code=202)
def refresh_topic_sentiment(
    audience_id: UUID,
    topic_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Força reprocessamento da análise de sentimento.
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
    sentiment_repo = TopicSentimentRepository(db)
    latest = sentiment_repo.find_latest_by_topic(topic_id)
    if latest and latest.status == "processing":
        return {
            "status": "processing",
            "message": "Já existe uma análise em andamento.",
            "analysis_id": str(latest.id),
        }

    trigger = TriggerSentimentUseCase(db)
    result = trigger.execute(topic_id, audience_id, force=True, language=current_user.preferred_language)

    return result
