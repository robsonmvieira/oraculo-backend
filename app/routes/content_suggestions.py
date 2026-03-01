"""Rotas para sugestões inteligentes de conteúdo."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.content_suggestions.application.use_cases.trigger_suggestions_use_case.trigger_suggestions_use_case import (
    TriggerSuggestionsUseCase,
)
from app.modules.content_suggestions.infra.repositories.content_suggestion_repository import (
    ContentSuggestionRepository,
)
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.domain.entities.user import User
from app.modules.shared.infra.database.database import get_db

router = APIRouter(
    prefix="/audiences",
    tags=["content-suggestions"],
)

AUDIENCE_NOT_FOUND = "Audiência não encontrada"
VALID_PRIORITIES = ("high", "medium", "low")
VALID_FORMATS = ("thread", "carrossel", "artigo", "video_script", "newsletter", "infographic")
VALID_FEEDBACK = ("useful", "not_useful", "used")


class FeedbackBody(BaseModel):
    status: str


def _check_ownership(audience, current_user: User) -> None:
    """Verifica se o usuário é dono da audiência."""
    if str(audience.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Acesso negado a esta audiência")


@router.post("/{audience_id}/content-suggestions/refresh", status_code=202)
def refresh_suggestions(
    audience_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Dispara geração de sugestões de conteúdo em background.
    Requer pelo menos 1 análise de tópicos ready.
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    trigger = TriggerSuggestionsUseCase(db)
    result = trigger.execute(
        audience_id=audience_id,
        user_id=current_user.id,
        language=current_user.preferred_language,
    )

    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])

    return result


@router.get("/{audience_id}/content-suggestions")
def list_suggestions(
    audience_id: UUID,
    priority: str | None = Query(None, description="Filter: high, medium, low"),
    format: str | None = Query(None, description="Filter: thread, carrossel, artigo, etc."),
    feedback_status: str | None = Query(None, description="Filter: useful, not_useful, used, null"),
    limit: int = Query(10, le=50),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista sugestões da análise mais recente."""
    if priority and priority not in VALID_PRIORITIES:
        raise HTTPException(
            status_code=400,
            detail=f"Prioridade inválida. Use: {', '.join(VALID_PRIORITIES)}",
        )
    if format and format not in VALID_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato inválido. Use: {', '.join(VALID_FORMATS)}",
        )

    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    suggestion_repo = ContentSuggestionRepository(db)
    latest = suggestion_repo.find_latest_by_audience(audience_id)

    if not latest:
        return {
            "status": "no_analysis",
            "message": "Nenhuma sugestão encontrada. Execute /refresh primeiro.",
            "suggestions": [],
        }

    if latest.status == "processing":
        return {
            "status": "processing",
            "message": "Sugestões em geração. Tente novamente em alguns minutos.",
            "analysis_id": str(latest.id),
            "suggestions": [],
        }

    if latest.status == "failed":
        return {
            "status": "failed",
            "message": f"Geração falhou: {latest.error_message or 'erro desconhecido'}",
            "suggestions": [],
        }

    suggestions = suggestion_repo.get_suggestions(
        analysis_id=latest.id,
        priority=priority,
        format_=format,
        feedback_status=feedback_status,
        limit=limit,
        offset=offset,
    )
    total = suggestion_repo.count_suggestions(
        analysis_id=latest.id,
        priority=priority,
        format_=format,
        feedback_status=feedback_status,
    )

    return {
        "analysis": {
            "id": str(latest.id),
            "status": latest.status,
            "modules_used": latest.modules_used,
            "model_used": latest.model_used,
            "created_at": latest.created_at.isoformat() if latest.created_at else None,
        },
        "suggestions": [_serialize_suggestion(s) for s in suggestions],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{audience_id}/content-suggestions/{suggestion_id}")
def get_suggestion(
    audience_id: UUID,
    suggestion_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Detalhe completo de uma sugestão."""
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    suggestion_repo = ContentSuggestionRepository(db)
    suggestion = suggestion_repo.get_suggestion_by_id(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Sugestão não encontrada")

    return _serialize_suggestion(suggestion)


@router.post("/{audience_id}/content-suggestions/{suggestion_id}/feedback")
def submit_feedback(
    audience_id: UUID,
    suggestion_id: UUID,
    body: FeedbackBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Registra feedback do usuário sobre uma sugestão."""
    if body.status not in VALID_FEEDBACK:
        raise HTTPException(
            status_code=400,
            detail=f"Status inválido. Use: {', '.join(VALID_FEEDBACK)}",
        )

    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    suggestion_repo = ContentSuggestionRepository(db)
    suggestion = suggestion_repo.update_feedback(suggestion_id, body.status)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Sugestão não encontrada")

    return {
        "suggestion_id": str(suggestion.id),
        "feedback_status": suggestion.feedback_status,
        "feedback_at": suggestion.feedback_at.isoformat() if suggestion.feedback_at else None,
    }


def _serialize_suggestion(s) -> dict:
    """Serializa uma sugestão para resposta JSON."""
    return {
        "id": str(s.id),
        "rank": s.rank,
        "priority": s.priority,
        "title": s.title,
        "approach": s.approach,
        "why_now": s.why_now,
        "evidence": s.evidence,
        "format": s.format,
        "format_rationale": s.format_rationale,
        "emotional_tone": s.emotional_tone,
        "tone_rationale": s.tone_rationale,
        "outline": s.outline,
        "keywords": s.keywords,
        "research_notes": s.research_notes,
        "image_prompt": s.image_prompt,
        "differentiation_notes": s.differentiation_notes,
        "accuracy_notes": s.accuracy_notes,
        "source_topics": s.source_topics,
        "source_modules": s.source_modules,
        "feedback_status": s.feedback_status,
        "feedback_at": s.feedback_at.isoformat() if s.feedback_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }
