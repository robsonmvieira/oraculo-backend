"""Rotas para análise temporal de temas (Hot Discussions & Top Content)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.domain.entities.user import User
from app.modules.shared.infra.database.database import get_db
from app.modules.theme_analysis.application.use_cases.trigger_theme_analysis_use_case import (
    TriggerThemeAnalysisUseCase,
)
from app.modules.theme_analysis.infra.repositories.theme_analysis_repository import (
    ThemeAnalysisRepository,
)

router = APIRouter(
    prefix="/audiences",
    tags=["theme-analysis"],
)

AUDIENCE_NOT_FOUND = "Audiência não encontrada"
VALID_WINDOWS = ("week", "month")


def _check_ownership(audience, current_user: User) -> None:
    """Verifica se o usuário é dono da audiência."""
    if str(audience.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Acesso negado a esta audiência")


@router.get("/{audience_id}/themes")
def list_themes(
    audience_id: UUID,
    window: str = Query("week", description="Janela temporal: week ou month"),
    sort_by: str = Query("rank", description="Ordenação: rank, engagement, post_count, name"),
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lista temas temporais de uma audiência.

    Retorna a análise mais recente para a janela temporal especificada.
    Se não existe ou está em processamento, retorna status correspondente.
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

    theme_repo = ThemeAnalysisRepository(db)
    latest = theme_repo.find_latest_by_audience_and_window(audience_id, window)

    if not latest:
        return {
            "status": "no_analysis",
            "message": f"Nenhuma análise de temas encontrada para {window}.",
            "themes": [],
            "total_themes": 0,
        }

    if latest.status == "processing":
        return {
            "status": "processing",
            "message": "Análise de temas em andamento. Tente novamente em alguns minutos.",
            "themes": [],
            "total_themes": 0,
        }

    if latest.status == "failed":
        return {
            "status": "failed",
            "message": f"Análise falhou: {latest.error_message or 'erro desconhecido'}",
            "themes": [],
            "total_themes": 0,
        }

    # Status ready — buscar temas
    themes = theme_repo.get_themes(
        analysis_id=latest.id,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )

    return {
        "status": "ready",
        "analysis_id": str(latest.id),
        "audience_id": str(audience_id),
        "time_window": latest.time_window,
        "period_start": str(latest.period_start) if latest.period_start else None,
        "period_end": str(latest.period_end) if latest.period_end else None,
        "completed_at": latest.completed_at.isoformat() if latest.completed_at else None,
        "total_themes": latest.total_themes,
        "themes": [
            {
                "id": str(t.id),
                "name": t.name,
                "summary": t.summary,
                "post_count": t.post_count,
                "avg_score": t.avg_score,
                "avg_comments": t.avg_comments,
                "engagement_score": t.engagement_score,
                "top_subreddits": t.top_subreddits,
                "top_keywords": t.top_keywords,
                "representative_posts": t.representative_posts,
                "rank": t.rank,
            }
            for t in themes
        ],
    }


@router.post("/{audience_id}/themes/refresh", status_code=202)
def refresh_themes(
    audience_id: UUID,
    window: str = Query("week", description="Janela temporal: week ou month"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Dispara análise temporal de temas para uma audiência.
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

    communities = audience_repo.get_communities(audience_id)
    if not communities:
        raise HTTPException(
            status_code=400,
            detail="Audiência não possui comunidades para análise",
        )

    trigger = TriggerThemeAnalysisUseCase(db)
    result = trigger.execute(
        audience_id=audience_id,
        window=window,
        language=current_user.preferred_language,
    )

    return result
