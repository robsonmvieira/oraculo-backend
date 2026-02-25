"""Estado do agente de extração de temas temporais."""

from typing import TypedDict


class PostData(TypedDict):
    id: str
    subreddit: str
    title: str
    selftext: str
    score: int
    num_comments: int
    created_utc: float
    permalink: str


class ExtractedTheme(TypedDict):
    name: str
    summary: str | None
    post_count: int
    avg_score: float
    avg_comments: float
    engagement_score: float | None
    top_subreddits: list[dict]  # [{"name": "sub", "post_count": N, "avg_score": N}]
    top_keywords: list[dict]  # [{"keyword": "...", "frequency": N}]
    representative_posts: list[
        dict
    ]  # [{"title": "...", "subreddit": "...", "score": N, "permalink": "..."}]
    rank: int | None


class ThemeExtractionState(TypedDict):
    audience_name: str
    audience_description: str | None
    community_names: list[str]
    posts: list[PostData]
    total_posts: int
    time_window: str  # "week" ou "month"
    period_start: str
    period_end: str
    language: str

    # Populados pelos nós
    extracted_themes: list[ExtractedTheme]
