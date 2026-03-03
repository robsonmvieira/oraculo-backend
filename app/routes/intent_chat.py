"""Routes for intent chat (conversational Q&A with history about intent categories)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.domain.entities.user import User
from app.modules.intent_chat.application.use_cases.send_intent_message_use_case.send_intent_message_use_case import (
    SendIntentMessageUseCase,
)
from app.modules.intent_chat.application.use_cases.start_intent_conversation_use_case.start_intent_conversation_use_case import (
    StartIntentConversationUseCase,
)
from app.modules.intent_chat.infra.repositories.intent_conversation_message_repository import (
    IntentConversationMessageRepository,
)
from app.modules.intent_chat.infra.repositories.intent_conversation_repository import (
    IntentConversationRepository,
)
from app.modules.shared.infra.database.database import get_db

router = APIRouter(prefix="/audiences", tags=["Intent Chat"])

AUDIENCE_NOT_FOUND = "Audiência não encontrada"
CONVERSATION_NOT_FOUND = "Conversa não encontrada"
VALID_WINDOWS = ("week", "month")
SUPPORTED_CHAT_CATEGORIES = ("pain_and_anger",)


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


@router.post("/{audience_id}/themes/intents/{category}/chat")
def start_conversation(
    audience_id: UUID,
    category: str,
    window: str = Query("week", description="Janela temporal: week ou month"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Inicia uma nova conversa sobre uma categoria de intenção.

    Retorna o conversation_id para enviar mensagens.
    """
    if window not in VALID_WINDOWS:
        raise HTTPException(
            status_code=400,
            detail=f"Janela inválida. Use: {', '.join(VALID_WINDOWS)}",
        )

    if category not in SUPPORTED_CHAT_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Chat não disponível para a categoria '{category}'. "
            f"Categorias suportadas: {', '.join(SUPPORTED_CHAT_CATEGORIES)}",
        )

    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    use_case = StartIntentConversationUseCase(db)
    result = use_case.execute(
        audience_id=audience_id,
        user_id=current_user.id,
        intent_category=category,
        window=window,
    )

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/{audience_id}/themes/intents/{category}/chat/{conversation_id}/messages")
def send_message(
    audience_id: UUID,
    category: str,
    conversation_id: UUID,
    body: SendMessageRequest,
    window: str = Query("week", description="Janela temporal: week ou month"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Envia uma mensagem na conversa e recebe a resposta da IA.

    A IA considera todo o historico da conversa para responder.
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

    conversation_repo = IntentConversationRepository(db)
    conversation = conversation_repo.find_by_id(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail=CONVERSATION_NOT_FOUND)

    _check_conversation_ownership(conversation, current_user)

    if not conversation.is_active:
        raise HTTPException(status_code=400, detail="Conversa arquivada")

    use_case = SendIntentMessageUseCase(db)
    result = use_case.execute(
        conversation_id=conversation_id,
        question=body.question,
        window=window,
        language=current_user.preferred_language,
    )

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/{audience_id}/themes/intents/{category}/chat")
def list_conversations(
    audience_id: UUID,
    category: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lista conversas do usuario para uma categoria de intenção.

    Retorna as conversas mais recentes primeiro.
    """
    audience_repo = AudienceRepository(db)
    audience = audience_repo.find_by_id(audience_id)
    if not audience:
        raise HTTPException(status_code=404, detail=AUDIENCE_NOT_FOUND)

    _check_ownership(audience, current_user)

    conversation_repo = IntentConversationRepository(db)
    conversations = conversation_repo.list_by_audience_category_and_user(
        audience_id=audience_id,
        intent_category=category,
        user_id=current_user.id,
    )

    return {
        "conversations": [
            {
                "conversation_id": str(c.id),
                "title": c.title,
                "intent_category": c.intent_category,
                "context_quality": c.context_quality,
                "is_active": c.is_active,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in conversations
        ]
    }


@router.get("/{audience_id}/themes/intents/{category}/chat/{conversation_id}/messages")
def list_messages(
    audience_id: UUID,
    category: str,
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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

    conversation_repo = IntentConversationRepository(db)
    conversation = conversation_repo.find_by_id(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail=CONVERSATION_NOT_FOUND)

    _check_conversation_ownership(conversation, current_user)

    message_repo = IntentConversationMessageRepository(db)
    messages = message_repo.list_by_conversation(conversation_id)

    return {
        "conversation_id": str(conversation_id),
        "title": conversation.title,
        "intent_category": conversation.intent_category,
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


@router.delete("/{audience_id}/themes/intents/{category}/chat/{conversation_id}")
def archive_conversation(
    audience_id: UUID,
    category: str,
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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

    conversation_repo = IntentConversationRepository(db)
    conversation = conversation_repo.find_by_id(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail=CONVERSATION_NOT_FOUND)

    _check_conversation_ownership(conversation, current_user)

    conversation_repo.deactivate(conversation_id)

    return {"status": "archived", "conversation_id": str(conversation_id)}
