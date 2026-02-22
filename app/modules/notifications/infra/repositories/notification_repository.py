"""Repositório para operações com notificações."""

import random
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.notifications.domain.entities.notification import Notification


class NotificationRepository:
    """Repositório para CRUD de notificações do usuário."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        user_id: UUID,
        type_: str,
        title: str,
        message: str,
        metadata: dict | None = None,
    ) -> Notification:
        """Cria e persiste uma nova notificação."""
        notification = Notification(
            user_id=user_id,
            type=type_,
            title=title,
            message=message,
            metadata_=metadata or {},
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def list_by_user(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False,
    ) -> list[Notification]:
        """Lista notificações do usuário, mais recentes primeiro."""
        query = self.db.query(Notification).filter(Notification.user_id == user_id)

        if unread_only:
            query = query.filter(Notification.is_read == False)  # noqa: E712

        notifications = (
            query.order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

        # Cleanup probabilístico: 1% das chamadas
        if random.random() < 0.01:
            self.delete_old_read(user_id)

        return notifications

    def count_unread(self, user_id: UUID) -> int:
        """Conta notificações não lidas do usuário."""
        return (
            self.db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
            .count()
        )

    def mark_read(self, notification_id: UUID, user_id: UUID) -> Notification | None:
        """Marca uma notificação como lida. Retorna None se não encontrada."""
        notification = (
            self.db.query(Notification)
            .filter(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
            .first()
        )
        if not notification:
            return None

        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def mark_all_read(self, user_id: UUID) -> int:
        """Marca todas as notificações não lidas como lidas. Retorna quantidade atualizada."""
        count = (
            self.db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
            .update(
                {
                    "is_read": True,
                    "read_at": datetime.now(timezone.utc),
                },
                synchronize_session="fetch",
            )
        )
        self.db.commit()
        return count

    def delete_old_read(self, user_id: UUID, days: int = 30) -> int:
        """Remove notificações lidas com mais de N dias."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        deleted = (
            self.db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.is_read == True,  # noqa: E712
                Notification.created_at < cutoff,
            )
            .delete(synchronize_session="fetch")
        )
        self.db.commit()
        return deleted
