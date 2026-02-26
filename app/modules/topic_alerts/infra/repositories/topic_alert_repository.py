"""Repositorio de alertas de topicos/temas."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.topic_alerts.domain.entities.topic_alert import TopicAlert

logger = logging.getLogger(__name__)


class TopicAlertRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        audience_id: UUID,
        user_id: UUID,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        metadata: dict | None = None,
    ) -> TopicAlert:
        """Cria um novo alerta."""
        alert = TopicAlert(
            audience_id=audience_id,
            user_id=user_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            metadata_=metadata or {},
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def create_batch(self, alerts: list[dict]) -> int:
        """Cria multiplos alertas em batch. Retorna quantidade criada."""
        objects = [TopicAlert(**a) for a in alerts]
        self.db.add_all(objects)
        self.db.commit()
        return len(objects)

    def list_by_audience(
        self,
        audience_id: UUID,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
        alert_type: str | None = None,
        severity: str | None = None,
        dismissed: bool | None = None,
    ) -> list[TopicAlert]:
        """Lista alertas da audiencia, mais recentes primeiro."""
        query = self.db.query(TopicAlert).filter(
            TopicAlert.audience_id == audience_id,
            TopicAlert.user_id == user_id,
        )

        if alert_type:
            query = query.filter(TopicAlert.alert_type == alert_type)
        if severity:
            query = query.filter(TopicAlert.severity == severity)
        if dismissed is not None:
            query = query.filter(TopicAlert.is_dismissed == dismissed)

        return (
            query.order_by(TopicAlert.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def get_summary(self, audience_id: UUID, user_id: UUID) -> dict:
        """Retorna contagem de alertas por tipo e severity (nao descartados)."""
        alerts = (
            self.db.query(TopicAlert)
            .filter(
                TopicAlert.audience_id == audience_id,
                TopicAlert.user_id == user_id,
                TopicAlert.is_dismissed == False,  # noqa: E712
            )
            .all()
        )

        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for a in alerts:
            by_type[a.alert_type] = by_type.get(a.alert_type, 0) + 1
            by_severity[a.severity] = by_severity.get(a.severity, 0) + 1

        return {
            "total": len(alerts),
            "by_type": by_type,
            "by_severity": by_severity,
        }

    def dismiss(self, alert_id: UUID, user_id: UUID) -> bool:
        """Marca alerta como descartado. Retorna True se encontrou."""
        alert = (
            self.db.query(TopicAlert)
            .filter(TopicAlert.id == alert_id, TopicAlert.user_id == user_id)
            .first()
        )
        if not alert:
            return False

        alert.is_dismissed = True
        self.db.commit()
        return True

    def find_recent_by_type(
        self,
        audience_id: UUID,
        alert_type: str,
        topic_name_normalized: str,
        hours: int = 24,
    ) -> TopicAlert | None:
        """
        Verifica se ja existe alerta recente para o mesmo topico/tipo.
        Evita alertas duplicados em re-execucoes proximas.
        """
        cutoff = datetime.now(timezone.utc).replace(
            hour=datetime.now(timezone.utc).hour - hours
            if datetime.now(timezone.utc).hour >= hours
            else 0
        )

        return (
            self.db.query(TopicAlert)
            .filter(
                TopicAlert.audience_id == audience_id,
                TopicAlert.alert_type == alert_type,
                TopicAlert.created_at >= cutoff,
                TopicAlert.metadata_["topic_name_normalized"].as_string()
                == topic_name_normalized,
            )
            .first()
        )
