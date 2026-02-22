from typing import TypedDict


class TopicSummary(TypedDict):
    name: str
    description: str
    communities: list[str]  # ["r/digital_marketing", ...]
    estimated_frequency: str
    growth_trend: str


class PostWithComments(TypedDict):
    id: str
    subreddit: str
    title: str
    selftext: str
    score: int
    num_comments: int
    created_utc: float
    permalink: str | None
    comments: list[dict]  # [{"body": "...", "score": N, "author": "..."}]


class PatternResult(TypedDict):
    summary: str
    co_occurrences: list[dict]
    # [{"topics": ["A", "B"], "frequency": "high", "context": "..."}]
    unanswered_questions: list[dict]
    # [{"question": "...", "frequency": "high", "communities": ["r/..."], "opportunity": "..."}]
    emerging_opinions: list[dict]
    # [{"opinion": "...", "support_level": "growing", "evidence": "...", "communities": ["r/..."]}]
    cross_community_gaps: list[dict]
    # [{"topic": "...", "discussed_in": ["r/..."], "missing_in": ["r/..."], "opportunity": "..."}]
    content_opportunities: list[dict]
    # [{"opportunity": "...", "type": "content|product|service", "confidence": "high|medium|low", "based_on": "..."}]


class PatternDetectionState(TypedDict):
    audience_name: str
    community_names: list[str]
    topics: list[TopicSummary]
    language: str

    # Populated by nodes
    posts_with_comments: list[PostWithComments]
    pattern_result: PatternResult | None
