"""Entidade de alerta inteligente de topico/tema."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSON, UUID

from app.modules.shared.infra.database.orm.metadata import Base


class TopicAlert(Base):
    """
    Alerta gerado automaticamente quando o sistema detecta eventos
    relevantes: topicos novos, crescimento explosivo ou temas emergentes.
    Persistido para historico e revisao futura.
    """

    __tablename__ = "topic_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audience_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audiences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alert_type = Column(String(40), nullable=False)
    severity = Column(String(10), nullable=False, default="info")
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)
    is_dismissed = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index(
            "ix_topic_alerts_audience_type",
            "audience_id",
            "alert_type",
        ),
        Index(
            "ix_topic_alerts_user_not_dismissed",
            "user_id",
            "is_dismissed",
            postgresql_where=(is_dismissed == False),  # noqa: E712
        ),
    )
