"""Estado do agente de classificação de intenção."""

from typing import TypedDict


class PostForClassification(TypedDict):
    """Post a ser classificado por intenção."""

    id: str
    subreddit: str
    title: str
    selftext: str
    score: int
    num_comments: int


class ClassifiedPost(TypedDict):
    """Resultado da classificação de um post."""

    post_id: str
    post_title: str
    post_subreddit: str
    primary_intent: str
    secondary_intent: str | None
    confidence: str  # high, medium, low


class IntentAggregation(TypedDict):
    """Resumo agregado de uma categoria de intenção."""

    category: str
    post_count: int
    description: str | None
    top_subreddits: list[dict]  # [{"name": "...", "count": N}]
    sample_posts: list[dict]  # [{"title": "...", "subreddit": "...", "score": N}]
    rank: int


class IntentClassificationState(TypedDict):
    """Estado do grafo de classificação de intenção."""

    # Inputs
    audience_name: str
    audience_description: str | None
    community_names: list[str]
    posts: list[PostForClassification]
    total_posts: int
    time_window: str
    period_start: str
    period_end: str
    language: str

    # Populated by nodes
    classified_posts: list[ClassifiedPost]
    intent_aggregations: list[IntentAggregation]
