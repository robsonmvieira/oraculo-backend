from typing import TypedDict


class SemanticSearchState(TypedDict):
    # Inputs
    audience_name: str
    community_names: list[str]
    language: str
    query: str
    matched_posts: list[dict]
    total_audience_posts: int

    # Populated by nodes
    context_quality: str
    answer: str | None
    patterns: list[dict] | None
