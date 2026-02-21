from typing import TypedDict


class CommunityInfo(TypedDict):
    name: str
    title: str | None
    description: str | None
    subscribers: int | None


class CandidateCommunity(TypedDict):
    name: str
    title: str | None
    description: str | None
    subscribers: int | None
    source: str  # "embedding", "related_subs", or "term_search"


class RankedSuggestion(TypedDict):
    name: str
    title: str | None
    description: str | None
    subscribers: int | None
    size_tag: str | None
    activity_tag: str | None
    growth_week: float | None
    relevance_score: float
    relevance_reason: str


class AudienceExpansionState(TypedDict):
    audience_id: str
    audience_name: str
    audience_description: str | None
    current_communities: list[CommunityInfo]
    excluded_names: list[str]
    user_id: str
    limit: int

    # Populated by nodes
    audience_theme: str
    candidates: list[CandidateCommunity]
    suggestions: list[RankedSuggestion]
