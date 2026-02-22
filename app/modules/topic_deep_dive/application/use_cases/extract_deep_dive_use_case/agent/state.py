from typing import TypedDict


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


class DeepDiveResult(TypedDict):
    summary: str
    subtopics: list[dict]
    # [{"name": "...", "description": "...", "post_count": N}]
    common_questions: list[dict]
    # [{"question": "...", "frequency": "high|medium|low", "example_context": "..."}]
    sentiment: dict
    # {"overall": "...", "positive_ratio": float, "negative_ratio": float,
    #  "neutral_ratio": float, "highlights": [...]}
    mentioned_products: list[dict]
    # [{"name": "...", "category": "...", "sentiment": "...", "mention_count": N, "context": "..."}]
    representative_posts: list[dict]
    # [{"title": "...", "subreddit": "...", "score": N, "permalink": "...", "excerpt": "..."}]
    actionable_insights: list[dict]
    # [{"insight": "...", "type": "opportunity|gap|trend|warning", "confidence": "high|medium|low"}]


class DeepDiveState(TypedDict):
    topic_name: str
    topic_description: str
    audience_name: str
    community_names: list[str]

    # Populated by nodes
    relevant_posts: list[PostWithComments]
    deep_dive_result: DeepDiveResult | None
