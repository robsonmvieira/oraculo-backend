import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audience_topics.infra.repositories.audience_topic_repository import (
    AudienceTopicRepository,
)
from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.topic_chat.application.use_cases.send_message_use_case.agent.chat_agent import (
    create_chat_agent,
)
from app.modules.topic_chat.infra.repositories.topic_conversation_message_repository import (
    TopicConversationMessageRepository,
)
from app.modules.topic_chat.infra.repositories.topic_conversation_repository import (
    TopicConversationRepository,
)
from app.modules.topic_deep_dive.infra.repositories.topic_deep_dive_repository import (
    TopicDeepDiveRepository,
)

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 40


class SendMessageUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.topic_repo = AudienceTopicRepository(db)
        self.deep_dive_repo = TopicDeepDiveRepository(db)
        self.conversation_repo = TopicConversationRepository(db)
        self.message_repo = TopicConversationMessageRepository(db)

    def execute(
        self,
        conversation_id: UUID,
        question: str,
        language: str = "en",
    ) -> dict:
        """
        Envia uma mensagem na conversa e retorna a resposta da IA.

        Returns:
            dict com answer, context_quality, message_id, conversation_id
        """
        conversation = self.conversation_repo.find_by_id(conversation_id)
        if not conversation:
            return {"error": "Conversation not found"}

        topic = self.topic_repo.get_topic_by_id(conversation.topic_id)
        if not topic:
            return {"error": "Topic not found"}

        audience = self.audience_repo.find_by_id(conversation.audience_id)
        if not audience:
            return {"error": "Audience not found"}

        communities = self.audience_repo.get_communities(conversation.audience_id)
        community_names = [c.subreddit_name for c in communities]

        # Persist user message
        self.message_repo.create(
            conversation_id=conversation_id,
            role="user",
            content=question,
        )

        # Load conversation history
        history_records = self.message_repo.list_by_conversation(
            conversation_id, limit=MAX_HISTORY_MESSAGES
        )
        messages = [
            {"role": msg.role, "content": msg.content} for msg in history_records
        ]

        # Build deep dive context
        deep_dive_context = None
        context_quality = "limited"

        latest_analysis = self.deep_dive_repo.find_latest_by_topic(
            conversation.topic_id
        )
        if latest_analysis and latest_analysis.status == "ready":
            deep_dive = self.deep_dive_repo.get_deep_dive(latest_analysis.id)
            if deep_dive:
                deep_dive_context = self._build_deep_dive_context(deep_dive)
                context_quality = "rich"

        # Run agent with conversation history
        agent = create_chat_agent()
        result = agent.invoke(
            {
                "topic_name": topic.name,
                "topic_description": topic.description or "",
                "audience_name": audience.name,
                "community_names": community_names,
                "language": language,
                "deep_dive_context": deep_dive_context,
                "context_quality": context_quality,
                "messages": messages,
                "answer": None,
            }
        )

        answer = result.get("answer", "")
        final_context_quality = result.get("context_quality", context_quality)

        # Persist assistant message
        assistant_msg = self.message_repo.create(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            context_quality=final_context_quality,
        )

        # Update conversation metadata
        self.conversation_repo.update_context_quality(
            conversation_id, final_context_quality
        )
        self.conversation_repo.touch(conversation_id)

        # Auto-generate title from first question
        if not conversation.title:
            title = question[:100].strip()
            if len(question) > 100:
                title += "..."
            self.conversation_repo.update_title(conversation_id, title)

        suggestion = None
        if final_context_quality == "limited":
            suggestion = (
                "Execute o Deep Dive neste topico para obter respostas "
                "mais detalhadas e baseadas em dados reais."
            )

        logger.info(
            "Topic Chat: answered in conversation '%s' (quality: %s)",
            conversation_id,
            final_context_quality,
        )

        return {
            "answer": answer,
            "context_quality": final_context_quality,
            "message_id": str(assistant_msg.id),
            "conversation_id": str(conversation_id),
            "suggestion": suggestion,
        }

    def _build_deep_dive_context(self, deep_dive) -> str:
        """Builds a text context from the deep dive data stored in the database."""
        sections = []

        if deep_dive.summary:
            sections.append(f"SUMMARY:\n{deep_dive.summary}")

        if deep_dive.subtopics:
            lines = ["SUBTOPICS IDENTIFIED:"]
            for st in deep_dive.subtopics:
                name = st.get("name", "")
                desc = st.get("description", "")
                count = st.get("post_count", 0)
                lines.append(f"- {name} ({count} posts): {desc}")
            sections.append("\n".join(lines))

        if deep_dive.common_questions:
            lines = ["FREQUENTLY ASKED QUESTIONS:"]
            for q in deep_dive.common_questions:
                question = q.get("question", "")
                freq = q.get("frequency", "")
                ctx = q.get("example_context", "")
                lines.append(f'- [{freq}] "{question}"')
                if ctx:
                    lines.append(f'  Context: "{ctx}"')
            sections.append("\n".join(lines))

        if deep_dive.mentioned_products:
            lines = ["MENTIONED TOOLS/PRODUCTS:"]
            for p in deep_dive.mentioned_products:
                name = p.get("name", "")
                cat = p.get("category", "")
                sentiment = p.get("sentiment", "")
                mentions = p.get("mention_count", 0)
                context = p.get("context", "")
                lines.append(
                    f"- {name} ({cat}, sentiment: {sentiment}, {mentions} mentions): {context}"
                )
            sections.append("\n".join(lines))

        if deep_dive.representative_posts:
            lines = ["REPRESENTATIVE POSTS:"]
            for p in deep_dive.representative_posts:
                title = p.get("title", "")
                sub = p.get("subreddit", "")
                score = p.get("score", 0)
                excerpt = p.get("excerpt", "")
                lines.append(f'- [r/{sub}, score:{score}] "{title}"')
                if excerpt:
                    lines.append(f'  Excerpt: "{excerpt}"')
            sections.append("\n".join(lines))

        if deep_dive.actionable_insights:
            lines = ["ACTIONABLE INSIGHTS:"]
            for i in deep_dive.actionable_insights:
                insight = i.get("insight", "")
                itype = i.get("type", "")
                confidence = i.get("confidence", "")
                lines.append(f"- [{itype}, {confidence} confidence] {insight}")
            sections.append("\n".join(lines))

        return "\n\n".join(sections)
