"""Routes for topic chat (conversational Q&A with history)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.modules.audience_topics.infra.repositories.audience_topic_repository import (
    AudienceTopicRepository,
)
from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.domain.entities.user import User
from app.modules.shared.infra.database.database import get_db
from app.modules.topic_chat.application.use_cases.send_message_use_case.send_message_use_case import (
    SendMessageUseCase,
)
from app.modules.topic_chat.application.use_cases.start_conversation_use_case.start_conversation_use_case import (
    StartConversationUseCase,
)
from app.modules.topic_chat.infra.repositories.topic_conversation_message_repository import (
    TopicConversationMessageRepository,
)
from app.modules.topic_chat.infra.repositories.topic_conversation_repository import (
    TopicConversationRepository,
)

router = APIRouter(prefix="/audiences", tags=["Topic Chat"])

AUDIENCE_NOT_FOUND = "Audience not found"
TOPIC_NOT_FOUND = "Topic not found"
CONVERSATION_NOT_FOUND = "Conversation not found"


class SendMessageRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)


def _check_ownership(audience, current_user: User) -> None:
    """Valida que o usuario e dono da audiencia ou superuser."""
    if current_user.is_superuser:
        return
    if audience.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso negado")


def _check_conversation_ownership(conversation, current_user: User) -> None:
    """Valida que o usuario e dono da conversa."""
    if current_user.is_superuser:
        return
    if conversation.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso negado")


@router.post("/{audience_id}/topics/{topic_id}/chat")
def start_conversation(
    audience_id: UUID,
    topic_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Inicia uma nova conversa sobre um topico.

    Retorna o conversation_id para enviar mensagens.
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    topic_repo = AudienceTopicRepository(db)
    topic = topic_repo.get_topic_by_id(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail=TOPIC_NOT_FOUND)

    use_case = StartConversationUseCase(db)
    result = use_case.execute(
        topic_id=topic_id,
        audience_id=audience_id,
        user_id=current_user.id,
    )

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/{audience_id}/topics/{topic_id}/chat/{conversation_id}/messages")
async def send_message(
    audience_id: UUID,
    topic_id: UUID,
    conversation_id: UUID,
    body: SendMessageRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Envia uma mensagem na conversa e recebe a resposta da IA.

    A IA considera todo o historico da conversa para responder.
    Suporta SSE streaming via header Accept: text/event-stream.
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    conversation_repo = TopicConversationRepository(db)
    conversation = conversation_repo.find_by_id(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail=CONVERSATION_NOT_FOUND)

    _check_conversation_ownership(conversation, current_user)

    if not conversation.is_active:
        raise HTTPException(status_code=400, detail="Conversation is archived")

    use_case = SendMessageUseCase(db)

    # Content negotiation: SSE streaming vs JSON
    accept = request.headers.get("accept", "")
    if "text/event-stream" in accept:
        return StreamingResponse(
            use_case.execute_streaming(
                conversation_id=conversation_id,
                question=body.question,
                language=current_user.preferred_language,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    result = use_case.execute(
        conversation_id=conversation_id,
        question=body.question,
        language=current_user.preferred_language,
    )

    if result.get("error"):
        detail = result.get("detail", result["error"])
        raise HTTPException(status_code=400, detail=detail)

    return result


@router.get("/{audience_id}/topics/{topic_id}/chat")
def list_conversations(
    audience_id: UUID,
    topic_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Lista conversas do usuario em um topico.

    Retorna as conversas mais recentes primeiro.
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    conversation_repo = TopicConversationRepository(db)
    conversations = conversation_repo.list_by_topic_and_user(
        topic_id=topic_id,
        user_id=current_user.id,
    )

    return {
        "conversations": [
            {
                "conversation_id": str(c.id),
                "title": c.title,
                "context_quality": c.context_quality,
                "is_active": c.is_active,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in conversations
        ]
    }


@router.get("/{audience_id}/topics/{topic_id}/chat/{conversation_id}/messages")
def list_messages(
    audience_id: UUID,
    topic_id: UUID,
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Lista mensagens de uma conversa.

    Retorna mensagens em ordem cronologica.
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    conversation_repo = TopicConversationRepository(db)
    conversation = conversation_repo.find_by_id(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail=CONVERSATION_NOT_FOUND)

    _check_conversation_ownership(conversation, current_user)

    message_repo = TopicConversationMessageRepository(db)
    messages = message_repo.list_by_conversation(conversation_id)

    return {
        "conversation_id": str(conversation_id),
        "title": conversation.title,
        "context_quality": conversation.context_quality,
        "is_active": conversation.is_active,
        "messages": [
            {
                "message_id": str(m.id),
                "role": m.role,
                "content": m.content,
                "context_quality": m.context_quality,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


@router.delete("/{audience_id}/topics/{topic_id}/chat/{conversation_id}")
def archive_conversation(
    audience_id: UUID,
    topic_id: UUID,
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Arquiva uma conversa (soft delete).

    A conversa nao sera mais listada como ativa, mas o historico e preservado.
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    conversation_repo = TopicConversationRepository(db)
    conversation = conversation_repo.find_by_id(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail=CONVERSATION_NOT_FOUND)

    _check_conversation_ownership(conversation, current_user)

    conversation_repo.deactivate(conversation_id)

    return {"status": "archived", "conversation_id": str(conversation_id)}
