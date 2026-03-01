"""Rotas para classificação de intenção de posts (Theme 02)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.domain.entities.user import User
from app.modules.intent_classification.application.use_cases.classify_intents_use_case.agent.intent_agent import (
    INTENT_CATEGORIES,
)
from app.modules.intent_classification.application.use_cases.trigger_intent_classification_use_case import (
    TriggerIntentClassificationUseCase,
)
from app.modules.intent_classification.infra.repositories.intent_classification_repository import (
    IntentClassificationRepository,
)
from app.modules.shared.infra.database.database import get_db

router = APIRouter(
    prefix="/audiences",
    tags=["intent-classification"],
)

AUDIENCE_NOT_FOUND = "Audiência não encontrada"
VALID_WINDOWS = ("week", "month")
VALID_INTENT_CATEGORIES = (
    "advice_request",
    "pain_and_anger",
    "solution_request",
    "self_promotion",
    "ideas",
    "news",
)


def _check_ownership(audience, current_user: User) -> None:
    """Verifica se o usuário é dono da audiência."""
    if str(audience.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Acesso negado a esta audiência")


@router.post("/{audience_id}/themes/intents/refresh", status_code=202)
def refresh_intents(
    audience_id: UUID,
    window: str = Query("week", description="Janela temporal: week ou month"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Dispara classificação de intenção dos posts de uma audiência.
    Requer que exista uma theme_analysis ready para a janela temporal.
    Retorna imediatamente com status 202.
    """
    if window not in VALID_WINDOWS:
        raise HTTPException(
            status_code=400,
            detail=f"Janela inválida. Use: {', '.join(VALID_WINDOWS)}",
        )

    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    trigger = TriggerIntentClassificationUseCase(db)
    result = trigger.execute(
        audience_id=audience_id,
        window=window,
        language=current_user.preferred_language,
    )

    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])

    return result


@router.get("/{audience_id}/themes/intents")
def list_intents(
    audience_id: UUID,
    window: str = Query("week", description="Janela temporal: week ou month"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lista categorias de intenção classificadas para uma audiência.

    Retorna a classificação mais recente para a janela temporal especificada.
    """
    if window not in VALID_WINDOWS:
        raise HTTPException(
            status_code=400,
            detail=f"Janela inválida. Use: {', '.join(VALID_WINDOWS)}",
        )

    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    intent_repo = IntentClassificationRepository(db)
    latest = intent_repo.find_latest_by_audience_and_window(audience_id, window)

    if not latest:
        return {
            "status": "no_analysis",
            "message": "Nenhuma classificação de intenções encontrada. Execute a análise de temas primeiro.",
            "intents": [],
        }

    if latest.status == "processing":
        return {
            "status": "processing",
            "message": "Classificação de intenções em andamento. Tente novamente em alguns minutos.",
            "intents": [],
        }

    if latest.status == "failed":
        return {
            "status": "failed",
            "message": f"Classificação falhou: {latest.error_message or 'erro desconhecido'}",
            "intents": [],
        }

    # Status ready — buscar resumos
    summaries = intent_repo.get_intent_summaries(latest.id)
    total_posts = latest.total_posts_classified or 0

    intents = []
    for s in summaries:
        cat_info = INTENT_CATEGORIES.get(s.intent_category, {})
        percentage = (
            round((s.post_count / total_posts) * 100, 1) if total_posts > 0 else 0.0
        )

        intents.append(
            {
                "category": s.intent_category,
                "label": cat_info.get("label", s.intent_category),
                "icon": cat_info.get("icon", "circle"),
                "post_count": s.post_count,
                "percentage": percentage,
                "description": s.description,
                "sample_posts": s.sample_posts or [],
                "top_subreddits": s.top_subreddits or [],
                "subcategories": s.subcategories or {},
                "topic_keywords": s.topic_keywords or {},
                "rank": s.rank,
            }
        )

    return {
        "status": "ready",
        "analysis_id": str(latest.id),
        "audience_id": str(audience_id),
        "time_window": latest.time_window,
        "completed_at": latest.completed_at.isoformat()
        if latest.completed_at
        else None,
        "total_posts_classified": total_posts,
        "intents": intents,
    }


@router.get("/{audience_id}/themes/intents/{category}/posts")
def list_intent_posts(
    audience_id: UUID,
    category: str,
    window: str = Query("week", description="Janela temporal: week ou month"),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lista posts classificados em uma categoria de intenção específica.
    Retorna lista paginada de posts.
    """
    if window not in VALID_WINDOWS:
        raise HTTPException(
            status_code=400,
            detail=f"Janela inválida. Use: {', '.join(VALID_WINDOWS)}",
        )

    if category not in VALID_INTENT_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Categoria inválida. Use: {', '.join(VALID_INTENT_CATEGORIES)}",
        )

    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    intent_repo = IntentClassificationRepository(db)
    latest = intent_repo.find_latest_by_audience_and_window(audience_id, window)

    if not latest or latest.status != "ready":
        raise HTTPException(
            status_code=404,
            detail="Nenhuma classificação pronta encontrada para esta janela temporal.",
        )

    posts = intent_repo.get_posts_by_intent(
        analysis_id=latest.id,
        intent_category=category,
        limit=limit,
        offset=offset,
    )
    total = intent_repo.count_posts_by_intent(latest.id, category)

    return {
        "posts": [
            {
                "post_reddit_id": p.post_reddit_id,
                "title": p.post_title,
                "subreddit": p.post_subreddit,
                "primary_intent": p.primary_intent,
                "secondary_intent": p.secondary_intent,
                "confidence": p.confidence,
            }
            for p in posts
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
