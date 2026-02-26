"""Routes for topic/theme intelligent alerts."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.domain.entities.user import User
from app.modules.shared.infra.database.database import get_db
from app.modules.topic_alerts.infra.repositories.topic_alert_repository import (
    TopicAlertRepository,
)

router = APIRouter(prefix="/audiences", tags=["Topic Alerts"])

AUDIENCE_NOT_FOUND = "Audience not found"


def _check_ownership(audience, current_user: User) -> None:
    """Valida que o usuario e dono da audiencia ou superuser."""
    if current_user.is_superuser:
        return
    if audience.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso negado")


@router.get("/{audience_id}/alerts")
def list_alerts(
    audience_id: UUID,
    alert_type: str | None = Query(None, description="Filter by alert type"),
    severity: str | None = Query(None, description="Filter by severity"),
    dismissed: bool | None = Query(None, description="Filter by dismissed status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Lista alertas da audiencia, mais recentes primeiro."""
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    repo = TopicAlertRepository(db)
    alerts = repo.list_by_audience(
        audience_id=audience_id,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        alert_type=alert_type,
        severity=severity,
        dismissed=dismissed,
    )

    return {
        "alerts": [
            {
                "id": str(a.id),
                "alert_type": a.alert_type,
                "severity": a.severity,
                "title": a.title,
                "message": a.message,
                "metadata": a.metadata_,
                "is_dismissed": a.is_dismissed,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in alerts
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/{audience_id}/alerts/summary")
def get_alerts_summary(
    audience_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Resumo de alertas: contagem por tipo e severity (nao descartados)."""
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    repo = TopicAlertRepository(db)
    return repo.get_summary(audience_id=audience_id, user_id=current_user.id)


@router.patch("/{audience_id}/alerts/{alert_id}/dismiss")
def dismiss_alert(
    audience_id: UUID,
    alert_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Marca um alerta como descartado."""
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    repo = TopicAlertRepository(db)
    dismissed = repo.dismiss(alert_id=alert_id, user_id=current_user.id)
    if not dismissed:
        raise HTTPException(status_code=404, detail="Alert not found")

    return {"status": "dismissed", "alert_id": str(alert_id)}
