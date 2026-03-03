from typing import TypedDict


class IntentAskState(TypedDict):
    intent_category: str
    audience_name: str
    community_names: list[str]
    language: str
    question: str

    # Intent classification + theme context (if available)
    intent_context: str | None

    # Populated by nodes
    context_quality: str  # "rich" or "limited"
    answer: str | None
