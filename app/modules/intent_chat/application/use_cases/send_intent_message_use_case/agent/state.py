from typing import TypedDict


class IntentChatState(TypedDict):
    intent_category: str
    audience_name: str
    community_names: list[str]
    language: str

    # Intent classification + theme context (if available)
    intent_context: str | None

    # Conversation history: [{"role": "user"|"assistant", "content": "..."}]
    messages: list[dict]

    # Populated by nodes
    context_quality: str  # "rich" or "limited"
    answer: str | None
