from typing import TypedDict


class TopicChatState(TypedDict):
    topic_name: str
    topic_description: str
    audience_name: str
    community_names: list[str]
    language: str

    # Context sources (if available)
    deep_dive_context: str | None
    sentiment_context: str | None
    pattern_context: str | None

    # Summary of older messages (when conversation exceeds MAX_HISTORY_MESSAGES)
    conversation_summary: str | None

    # Conversation history: [{"role": "user"|"assistant", "content": "..."}]
    messages: list[dict]

    # Populated by nodes
    context_quality: str  # "rich", "partial", or "limited"
    answer: str | None
