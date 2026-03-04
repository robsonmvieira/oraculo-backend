import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.intent_chat.application.use_cases.send_intent_message_use_case.agent.intent_chat_agent import (
    create_intent_chat_agent,
)
from app.modules.intent_chat.infra.repositories.intent_conversation_message_repository import (
    IntentConversationMessageRepository,
)
from app.modules.intent_chat.infra.repositories.intent_conversation_repository import (
    IntentConversationRepository,
)
from app.modules.intent_classification.infra.repositories.intent_classification_repository import (
    IntentClassificationRepository,
)
from app.modules.theme_analysis.infra.repositories.theme_analysis_repository import (
    ThemeAnalysisRepository,
)
from app.modules.theme_analysis.infra.repositories.theme_summary_repository import (
    ThemeSummaryRepository,
)

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 40


class SendIntentMessageUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.intent_repo = IntentClassificationRepository(db)
        self.theme_repo = ThemeAnalysisRepository(db)
        self.theme_summary_repo = ThemeSummaryRepository(db)
        self.conversation_repo = IntentConversationRepository(db)
        self.message_repo = IntentConversationMessageRepository(db)

    def execute(
        self,
        conversation_id: UUID,
        question: str,
        window: str = "week",
        language: str = "en",
    ) -> dict:
        """
        Envia uma mensagem na conversa e retorna a resposta da IA.

        Returns:
            dict com answer, context_quality, message_id, conversation_id, suggestion
        """
        conversation = self.conversation_repo.find_by_id(conversation_id)
        if not conversation:
            return {"error": "Conversation not found"}

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

        # Build intent context
        intent_context = None
        context_quality = "limited"

        intent_analysis = self.intent_repo.find_latest_by_audience_and_window(
            conversation.audience_id, window
        )
        if intent_analysis and intent_analysis.status == "ready":
            summaries = self.intent_repo.get_intent_summaries(intent_analysis.id)
            pain_summary = next(
                (
                    s
                    for s in summaries
                    if s.intent_category == conversation.intent_category
                ),
                None,
            )

            # Fetch theme summaries for broader context
            theme_summaries = []
            theme_analysis = self.theme_repo.find_latest_by_audience_and_window(
                conversation.audience_id, window
            )
            if theme_analysis and theme_analysis.status == "ready":
                themes = self.theme_repo.get_themes(theme_analysis.id, limit=3)
                for theme in themes:
                    ts = self.theme_summary_repo.find_by_theme_id(theme.id)
                    if ts:
                        theme_summaries.append(ts)

            if pain_summary:
                intent_context = self._build_intent_context(
                    pain_summary, conversation.intent_category, theme_summaries
                )
                context_quality = "rich"

        # Run agent with conversation history
        agent = create_intent_chat_agent()
        result = agent.invoke(
            {
                "intent_category": conversation.intent_category,
                "audience_name": audience.name,
                "community_names": community_names,
                "language": language,
                "intent_context": intent_context,
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
                "Execute a classificação de intenções para obter respostas "
                "mais detalhadas e baseadas em dados reais."
            )

        logger.info(
            "Intent Chat: answered in conversation '%s' (quality: %s)",
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

    _CATEGORY_LABELS = {
        "pain_and_anger": {
            "overview": "PAIN & ANGER OVERVIEW",
            "subcategories": "EMOTION BREAKDOWN",
            "topic_keywords": "PAIN TOPIC KEYWORDS",
            "patterns": "BEHAVIORAL PAIN PATTERNS",
            "top_subreddits": "TOP SUBREDDITS FOR PAIN & ANGER",
        },
        "solution_request": {
            "overview": "SOLUTION REQUESTS OVERVIEW",
            "subcategories": "SOLUTION TYPE BREAKDOWN",
            "topic_keywords": "SOLUTION TOPIC KEYWORDS",
            "patterns": "SOLUTION REQUEST PATTERNS",
            "top_subreddits": "TOP SUBREDDITS FOR SOLUTION REQUESTS",
        },
        "advice_request": {
            "overview": "ADVICE REQUESTS OVERVIEW",
            "subcategories": "ADVICE TYPE BREAKDOWN",
            "topic_keywords": "ADVICE TOPIC KEYWORDS",
            "patterns": "ADVICE REQUEST PATTERNS",
            "top_subreddits": "TOP SUBREDDITS FOR ADVICE REQUESTS",
        },
    }

    def _build_intent_context(
        self,
        intent_summary,
        intent_category: str = "pain_and_anger",
        theme_summaries: list | None = None,
    ) -> str:
        """Builds a text context from intent classification + theme data."""
        labels = self._CATEGORY_LABELS.get(intent_category, self._CATEGORY_LABELS["pain_and_anger"])
        sections = []

        # 1. Description
        if intent_summary.description:
            sections.append(f"{labels['overview']}:\n{intent_summary.description}")

        # 2. Subcategories
        if intent_summary.subcategories:
            lines = [f"{labels['subcategories']}:"]
            for name, count in sorted(
                intent_summary.subcategories.items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                lines.append(f"- {name}: {count} posts")
            sections.append("\n".join(lines))

        # 3. Topic Keywords
        if intent_summary.topic_keywords:
            lines = [f"{labels['topic_keywords']}:"]
            for keyword, count in sorted(
                intent_summary.topic_keywords.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:20]:
                lines.append(f"- {keyword}: {count} mentions")
            sections.append("\n".join(lines))

        # 4. Patterns (behavioral groups)
        if intent_summary.pain_patterns:
            lines = [f"{labels['patterns']}:"]
            for pattern in intent_summary.pain_patterns:
                name = pattern.get("name", "")
                emoji = pattern.get("emoji", "")
                post_count = pattern.get("post_count", 0)
                total_upvotes = pattern.get("total_upvotes", 0)
                total_comments = pattern.get("total_comments", 0)
                lines.append(
                    f"- {emoji} {name} ({post_count} posts, "
                    f"{total_upvotes} upvotes, {total_comments} comments)"
                )
                # Include up to 3 sample submissions per pattern
                for sub in pattern.get("submissions", [])[:3]:
                    title = sub.get("title", "")
                    subreddit = sub.get("subreddit", "")
                    score = sub.get("score", 0)
                    lines.append(f'  * [{subreddit}, score:{score}] "{title}"')
                    if sub.get("body"):
                        body_preview = sub["body"][:200]
                        lines.append(f'    Body: "{body_preview}..."')
            sections.append("\n".join(lines))

        # 5. Top Subreddits
        if intent_summary.top_subreddits:
            lines = [f"{labels['top_subreddits']}:"]
            for sr in intent_summary.top_subreddits:
                name = sr.get("name", "")
                count = sr.get("count", 0)
                lines.append(f"- {name}: {count} posts")
            sections.append("\n".join(lines))

        # 6. Sample Posts
        if intent_summary.sample_posts:
            lines = ["SAMPLE POSTS:"]
            for post in intent_summary.sample_posts[:10]:
                title = post.get("title", "")
                subreddit = post.get("subreddit", "")
                lines.append(f'- [r/{subreddit}] "{title}"')
            sections.append("\n".join(lines))

        # 7. Theme Summaries (broader narrative context)
        if theme_summaries:
            lines = ["BROADER THEME CONTEXT:"]
            for ts in theme_summaries[:3]:
                if ts.narrative:
                    lines.append(f"\nTheme Narrative:\n{ts.narrative[:500]}")
                if ts.key_themes:
                    for kt in ts.key_themes[:3]:
                        theme_name = kt.get("theme", "")
                        desc = kt.get("description", "")
                        lines.append(f"  - {theme_name}: {desc}")
            sections.append("\n".join(lines))

        return "\n\n".join(sections)
