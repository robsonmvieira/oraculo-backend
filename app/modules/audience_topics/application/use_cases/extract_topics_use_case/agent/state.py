from typing import TypedDict


class PostData(TypedDict):
    id: str
    subreddit: str
    title: str
    selftext: str
    score: int
    num_comments: int
    created_utc: float


class ExtractedTopic(TypedDict):
    name: str
    description: str
    growth_percentage: float | None
    mention_frequency: float | None
    mention_period: str | None  # "day", "week", "month"
    post_count: int
    communities: list[dict]  # [{"name": "sub", "post_count": N}]
    rank: int


class TopicExtractionState(TypedDict):
    audience_name: str
    audience_description: str | None
    community_names: list[str]
    posts: list[PostData]
    total_posts: int

    # Populated by nodes
    extracted_topics: list[ExtractedTopic]
