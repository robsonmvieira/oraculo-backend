from typing import TypedDict


class TopicAskState(TypedDict):
    topic_name: str
    topic_description: str
    audience_name: str
    community_names: list[str]
    language: str
    question: str

    # Deep dive context (if available)
    deep_dive_context: str | None

    # Populated by nodes
    context_quality: str  # "rich" or "limited"
    answer: str | None
