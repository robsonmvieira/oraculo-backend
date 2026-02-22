"""Rotas de notificações: SSE para tempo real + REST para CRUD."""

import asyncio
import json
import logging
import os
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from redis import Redis
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.domain.entities.user import User
from app.modules.identity.infra.repositories.user_repository import UserRepository
from app.modules.notifications.infra.repositories.notification_repository import (
    NotificationRepository,
)
from app.modules.shared.infra.database.database import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ---------------------------------------------------------------------------
# SSE — Server-Sent Events
# ---------------------------------------------------------------------------


def _authenticate_sse_token(token: str, db: Session) -> User:
    """Valida JWT recebido via query param para conexões SSE."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido"
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token não é do tipo access",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido"
        )

    repo = UserRepository(db)
    user = repo.find_by_id(UUID(user_id))

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado ou desativado",
        )

    return user


@router.get("/stream")
async def sse_stream(
    request: Request,
    token: str = Query(..., description="JWT access token"),
):
    """Endpoint SSE para notificações em tempo real."""
    db = SessionLocal()
    try:
        user = _authenticate_sse_token(token, db)
        user_id = user.id
    finally:
        db.close()

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    async def event_generator():
        r = Redis.from_url(redis_url, decode_responses=True)
        pubsub = r.pubsub()
        channel = f"notifications:{user_id}"
        pubsub.subscribe(channel)

        heartbeat_counter = 0

        try:
            while True:
                if await request.is_disconnected():
                    break

                message = pubsub.get_message(timeout=1.0)
                if message and message["type"] == "message":
                    data = message["data"]
                    parsed = json.loads(data)
                    event_id = parsed.get("id", "")
                    yield f"id: {event_id}\nevent: notification\ndata: {data}\n\n"
                    heartbeat_counter = 0
                else:
                    heartbeat_counter += 1
                    # Heartbeat a cada ~30 segundos (30 iterações de 1s)
                    if heartbeat_counter >= 30:
                        yield ": heartbeat\n\n"
                        heartbeat_counter = 0

                await asyncio.sleep(1)
        finally:
            pubsub.unsubscribe(channel)
            pubsub.close()
            r.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# REST — CRUD de notificações
# ---------------------------------------------------------------------------


@router.get("")
def list_notifications(
    limit: int = 50,
    offset: int = 0,
    unread_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista notificações do usuário autenticado."""
    repo = NotificationRepository(db)
    notifications = repo.list_by_user(
        current_user.id, limit=limit, offset=offset, unread_only=unread_only
    )
    return {
        "notifications": [
            {
                "id": str(n.id),
                "type": n.type,
                "title": n.title,
                "message": n.message,
                "metadata": n.metadata_,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
                "read_at": n.read_at.isoformat() if n.read_at else None,
            }
            for n in notifications
        ],
    }


@router.get("/unread-count")
def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna contagem de notificações não lidas."""
    repo = NotificationRepository(db)
    count = repo.count_unread(current_user.id)
    return {"unread_count": count}


@router.patch("/{notification_id}/read")
def mark_notification_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Marca uma notificação como lida."""
    repo = NotificationRepository(db)
    notification = repo.mark_read(notification_id, current_user.id)
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificação não encontrada",
        )
    return {"marked_read": True}


@router.patch("/read-all")
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Marca todas as notificações do usuário como lidas."""
    repo = NotificationRepository(db)
    count = repo.mark_all_read(current_user.id)
    return {"marked_read": count}
