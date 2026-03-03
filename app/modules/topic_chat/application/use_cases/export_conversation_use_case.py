import re
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audience_topics.infra.repositories.audience_topic_repository import (
    AudienceTopicRepository,
)
from app.modules.topic_chat.infra.repositories.topic_conversation_message_repository import (
    TopicConversationMessageRepository,
)
from app.modules.topic_chat.infra.repositories.topic_conversation_repository import (
    TopicConversationRepository,
)


class ExportConversationUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.conversation_repo = TopicConversationRepository(db)
        self.message_repo = TopicConversationMessageRepository(db)
        self.topic_repo = AudienceTopicRepository(db)

    def execute(self, conversation_id: UUID) -> dict:
        """
        Exporta uma conversa completa como markdown.

        Returns:
            dict com 'content' (str), 'filename' (str) e 'title' (str),
            ou dict com 'error' se conversa nao encontrada.
        """
        conversation = self.conversation_repo.find_by_id(conversation_id)
        if not conversation:
            return {"error": "Conversation not found"}

        topic = self.topic_repo.get_topic_by_id(conversation.topic_id)
        topic_name = topic.name if topic else "Unknown Topic"

        messages = self.message_repo.list_all_by_conversation(conversation_id)

        title = conversation.title or "Untitled Conversation"
        created_at = conversation.created_at.strftime("%Y-%m-%d %H:%M")
        context_quality = conversation.context_quality or "unknown"

        # Build markdown
        lines = [
            f"# {title}",
            "",
            f"**Topic:** {topic_name}",
            f"**Date:** {created_at}",
            f"**Messages:** {len(messages)}",
            f"**Quality:** {context_quality}",
            "",
            "---",
        ]

        for msg in messages:
            role_label = "User" if msg.role == "user" else "Assistant"
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M")
            lines.append("")
            lines.append(f"**{role_label}** — {timestamp}")
            lines.append("")
            lines.append(msg.content)
            lines.append("")
            lines.append("---")

        content = "\n".join(lines) + "\n"

        # Sanitize filename
        slug = re.sub(r"[^\w\s-]", "", title.lower())
        slug = re.sub(r"[\s_]+", "-", slug).strip("-")[:50]
        date_str = conversation.created_at.strftime("%Y%m%d")
        filename = f"chat-{slug}-{date_str}.md"

        return {
            "content": content,
            "filename": filename,
            "title": title,
        }
