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
from app.modules.theme_analysis.application.use_cases.trigger_theme_summary_use_case import (
    TriggerThemeSummaryUseCase,
)
from app.modules.theme_analysis.application.use_cases.trigger_theme_panel_use_case import (
    TriggerThemePanelUseCase,
)
from app.modules.theme_analysis.infra.repositories.theme_analysis_repository import (
    ThemeAnalysisRepository,
)
from app.modules.theme_analysis.infra.repositories.theme_panel_repository import (
    ThemePanelRepository,
)
from app.modules.theme_analysis.infra.repositories.theme_summary_repository import (
    ThemeSummaryRepository,
)

router = APIRouter(
    prefix="/audiences",
    tags=["theme-analysis"],
)

AUDIENCE_NOT_FOUND = "Audiência não encontrada"
VALID_WINDOWS = ("week", "month")
WINDOW_QUERY_DESC = "Janela temporal: week ou month"


def _check_ownership(audience, current_user: User) -> None:
    """Verifica se o usuário é dono da audiência."""
    if str(audience.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Acesso negado a esta audiência")


@router.get("/{audience_id}/themes")
def list_themes(
    audience_id: UUID,
    window: str = Query("week", description=WINDOW_QUERY_DESC),
    sort_by: str = Query(
        "rank", description="Ordenação: rank, engagement, post_count, name"
    ),
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
        "completed_at": latest.completed_at.isoformat()
        if latest.completed_at
        else None,
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
    window: str = Query("week", description=WINDOW_QUERY_DESC),
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


@router.get("/{audience_id}/themes/{theme_id}/summary")
def get_theme_summary(
    audience_id: UUID,
    theme_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retorna o sumário narrativo enriquecido de um tema.

    Se não existe sumário, retorna status 'no_summary'.
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    summary_repo = ThemeSummaryRepository(db)
    summary = summary_repo.find_by_theme_id(theme_id)

    if not summary:
        return {
            "status": "no_summary",
            "message": "Nenhum sumário encontrado para este tema. Dispare a geração primeiro.",
        }

    return {
        "status": "ready",
        "theme_id": str(summary.theme_id),
        "narrative": summary.narrative,
        "highlights": summary.highlights,
        "emotional_tone": summary.emotional_tone,
        "tone_description": summary.tone_description,
        "key_themes": summary.key_themes,
        "intent_breakdown": summary.intent_breakdown,
        "week_differentiator": summary.week_differentiator,
        "created_at": summary.created_at.isoformat() if summary.created_at else None,
    }


@router.post("/{audience_id}/themes/{theme_id}/summary/refresh", status_code=202)
def refresh_theme_summary(
    audience_id: UUID,
    theme_id: UUID,
    window: str = Query("week", description=WINDOW_QUERY_DESC),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Dispara geração de sumário narrativo enriquecido para um tema.
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

    trigger = TriggerThemeSummaryUseCase(db)
    result = trigger.execute(
        audience_id=audience_id,
        theme_id=theme_id,
        window=window,
        language=current_user.preferred_language,
    )

    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])

    return result


@router.get("/{audience_id}/themes/{theme_id}/panel")
def get_theme_panel(
    audience_id: UUID,
    theme_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retorna os dados estruturados do painel de um tema.

    Inclui subcategorias, tópicos relacionados e distribuição de subreddits.
    Se não existe painel, retorna status 'no_panel'.
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    panel_repo = ThemePanelRepository(db)
    panel = panel_repo.find_by_theme_id(theme_id)

    if not panel:
        return {
            "status": "no_panel",
            "message": "Nenhum painel encontrado para este tema. Dispare a geração primeiro.",
        }

    return {
        "status": "ready",
        "theme_id": str(panel.theme_id),
        "subcategories": {
            "total": len(panel.subcategories) if panel.subcategories else 0,
            "items": panel.subcategories or [],
        },
        "related_topics": {
            "total": len(panel.related_topics) if panel.related_topics else 0,
            "items": panel.related_topics or [],
        },
        "subreddit_distribution": {
            "total": len(panel.subreddit_distribution)
            if panel.subreddit_distribution
            else 0,
            "items": panel.subreddit_distribution or [],
        },
        "actions": panel.action_links or {},
        "created_at": panel.created_at.isoformat() if panel.created_at else None,
    }


@router.post("/{audience_id}/themes/{theme_id}/panel/refresh", status_code=202)
def refresh_theme_panel(
    audience_id: UUID,
    theme_id: UUID,
    window: str = Query("week", description=WINDOW_QUERY_DESC),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Dispara geração de dados estruturados do painel para um tema.
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

    trigger = TriggerThemePanelUseCase(db)
    result = trigger.execute(
        audience_id=audience_id,
        theme_id=theme_id,
        window=window,
        language=current_user.preferred_language,
    )

    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])

    return result


def _build_default_actions(audience_id: UUID, theme_id: UUID) -> dict:
    """Monta action links padrão quando não há painel salvo."""
    return {
        "view_all": f"/audiences/{audience_id}/topics?theme_filter={theme_id}",
        "patterns": f"/audiences/{audience_id}/patterns",
        "ask": f"/audiences/{audience_id}/topics/ask",
        "copy_summary": True,
    }


def _serialize_summary(summary) -> dict:
    """Serializa sumário narrativo para resposta da API."""
    if not summary:
        return {"status": "no_summary"}
    return {
        "status": "ready",
        "narrative": summary.narrative,
        "emotional_tone": summary.emotional_tone,
        "tone_description": summary.tone_description,
        "highlights": summary.highlights,
        "key_themes": summary.key_themes,
        "intent_breakdown": summary.intent_breakdown,
        "week_differentiator": summary.week_differentiator,
    }


def _serialize_panel(panel) -> dict:
    """Serializa painel de dados estruturados para resposta da API."""
    if not panel:
        return {"status": "no_panel"}
    return {
        "status": "ready",
        "subcategories": panel.subcategories,
        "related_topics": panel.related_topics,
        "subreddit_distribution": panel.subreddit_distribution,
    }


def _find_ready_analysis(theme_repo, audience_id: UUID):
    """Busca análise de temas ready, tentando week e depois month."""
    for window in VALID_WINDOWS:
        analysis = theme_repo.find_latest_by_audience_and_window(audience_id, window)
        if analysis and analysis.status == "ready":
            return analysis
    return None


@router.get("/{audience_id}/themes/{theme_id}/full")
def get_theme_full(
    audience_id: UUID,
    theme_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retorna dados completos de um tema: metadados + sumário + painel.

    Endpoint combinado para o frontend carregar o painel direito em um único request.
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    theme_repo = ThemeAnalysisRepository(db)
    latest = _find_ready_analysis(theme_repo, audience_id)
    if not latest:
        raise HTTPException(
            status_code=404,
            detail="Nenhuma análise de temas encontrada.",
        )

    themes = theme_repo.get_themes(analysis_id=latest.id)
    theme = next((t for t in themes if str(t.id) == str(theme_id)), None)
    if not theme:
        raise HTTPException(status_code=404, detail="Tema não encontrado.")

    summary = ThemeSummaryRepository(db).find_by_theme_id(theme_id)
    panel = ThemePanelRepository(db).find_by_theme_id(theme_id)

    return {
        "theme": {
            "id": str(theme.id),
            "name": theme.name,
            "summary": theme.summary,
            "time_window": latest.time_window,
            "period_start": str(latest.period_start) if latest.period_start else None,
            "period_end": str(latest.period_end) if latest.period_end else None,
            "post_count": theme.post_count,
            "avg_score": theme.avg_score,
            "avg_comments": theme.avg_comments,
            "engagement_score": theme.engagement_score,
            "top_keywords": theme.top_keywords,
            "rank": theme.rank,
        },
        "summary": _serialize_summary(summary),
        "panel": _serialize_panel(panel),
        "actions": panel.action_links
        if panel
        else _build_default_actions(audience_id, theme_id),
    }
