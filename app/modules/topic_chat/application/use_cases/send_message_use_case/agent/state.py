from typing import TypedDict


class TopicChatState(TypedDict):
    topic_name: str
    topic_description: str
    audience_name: str
    community_names: list[str]
    language: str

    # Deep dive context (if available)
    deep_dive_context: str | None

    # Conversation history: [{"role": "user"|"assistant", "content": "..."}]
    messages: list[dict]

    # Populated by nodes
    context_quality: str  # "rich" or "limited"
    answer: str | None
