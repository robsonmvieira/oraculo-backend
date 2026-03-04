"""Routes for YouTube cross-platform validation."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.modules.youtube_validation.application.use_cases.trigger_youtube_validation_use_case import (
    TriggerYouTubeValidationUseCase,
)
from app.modules.youtube_validation.infra.repositories.youtube_validation_repository import (
    YouTubeValidationRepository,
)
from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.domain.entities.user import User
from app.modules.shared.infra.database.database import get_db

router = APIRouter(prefix="/audiences", tags=["YouTube Validation"])

AUDIENCE_NOT_FOUND = "Audience not found"


def _check_ownership(audience, current_user: User) -> None:
    """Valida que o usuário é dono da audiência ou superuser."""
    if current_user.is_superuser:
        return
    if audience.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso negado")


@router.post("/{audience_id}/youtube-validation", status_code=202)
def trigger_youtube_validation(
    audience_id: UUID,
    force: bool = False,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Dispara validação cross-platform YouTube para a audiência.

    Coleta vídeos, comentários e transcrições do YouTube para cada tópico
    e cruza com dados Reddit existentes. Retorna 202 indicando que o
    processamento está em andamento.
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    trigger = TriggerYouTubeValidationUseCase(db)
    result = trigger.execute(
        audience_id=audience_id,
        user_id=current_user.id,
        force=force,
        language=current_user.preferred_language,
    )

    return result


@router.get("/{audience_id}/youtube-validation")
def get_youtube_validation(
    audience_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Retorna o resultado mais recente da validação YouTube.

    Retorna status: no_analysis | processing | failed | ready.
    Quando ready, inclui analysis_data e summary.
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    validation_repo = YouTubeValidationRepository(db)
    latest = validation_repo.find_latest_by_audience(audience_id)

    if not latest:
        return {
            "status": "no_analysis",
            "message": "No YouTube validation found. Trigger one first.",
            "audience_id": str(audience_id),
        }

    if latest.status == "processing":
        return {
            "status": "processing",
            "message": "YouTube validation in progress. Check back in a few minutes.",
            "validation_id": str(latest.id),
            "audience_id": str(audience_id),
        }

    if latest.status == "failed":
        return {
            "status": "failed",
            "message": f"Validation failed: {latest.error_message or 'unknown error'}",
            "validation_id": str(latest.id),
            "audience_id": str(audience_id),
        }

    return {
        "status": "ready",
        "validation_id": str(latest.id),
        "audience_id": str(audience_id),
        "completed_at": (
            latest.completed_at.isoformat() if latest.completed_at else None
        ),
        "model_used": latest.model_used,
        "total_videos": latest.total_videos,
        "total_comments": latest.total_comments,
        "analysis_data": latest.analysis_data,
        "summary": latest.summary,
    }


@router.get("/{audience_id}/youtube-validation/{topic_name}/videos")
def get_youtube_validation_videos(
    audience_id: UUID,
    topic_name: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Retorna vídeos coletados para um tópico específico da validação mais recente.

    Útil para browse detalhado dos vídeos por tópico.
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    validation_repo = YouTubeValidationRepository(db)
    latest = validation_repo.find_latest_by_audience(audience_id)

    if not latest or latest.status != "ready":
        return {
            "status": "no_data",
            "message": "No ready YouTube validation found.",
            "topic_name": topic_name,
            "videos": [],
        }

    videos = validation_repo.get_collected_videos_by_topic(latest.id, topic_name)

    return {
        "status": "ready",
        "validation_id": str(latest.id),
        "topic_name": topic_name,
        "videos_count": len(videos),
        "videos": [
            {
                "id": str(v.id),
                "video_id": v.video_id,
                "title": v.title,
                "channel_name": v.channel_name,
                "views": v.views,
                "likes": v.likes,
                "duration_seconds": v.duration_seconds,
                "tags": v.tags,
                "description": v.description,
                "comments_count": len(v.comments) if v.comments else 0,
                "has_transcript": v.transcript is not None,
                "transcript_lang": v.transcript_lang,
                "published_at": (
                    v.published_at.isoformat() if v.published_at else None
                ),
            }
            for v in videos
        ],
    }
