"""Entidade de notificação persistida no PostgreSQL."""

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


class Notification(Base):
    """
    Notificação do usuário. Criada automaticamente quando processos
    assíncronos (análises, extração de tópicos, etc.) finalizam.
    Entregue em tempo real via SSE e persistida para controle de lida/não lida.
    """

    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type = Column(String(60), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    read_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "ix_notifications_user_unread",
            "user_id",
            "is_read",
            postgresql_where=(is_read == False),  # noqa: E712
        ),
    )
