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


class SentimentResult(TypedDict):
    overall_sentiment: dict
    # {"score": "positive|negative|neutral|mixed", "positive_ratio": float,
    #  "negative_ratio": float, "neutral_ratio": float}
    emotional_map: list[dict]
    # [{"emotion": "...", "intensity": "high|medium|low", "percentage": float, "example": "..."}]
    sentiment_by_community: list[dict]
    # [{"community": "r/...", "positive": float, "negative": float, "neutral": float, "dominant_emotion": "..."}]
    sentiment_by_subtopic: list[dict]
    # [{"subtopic": "...", "sentiment": "...", "score": float, "key_driver": "..."}]
    sentiment_drivers: dict
    # {"positive": [{"driver": "...", "frequency": "...", "mentions": N, "example_quote": "..."}],
    #  "negative": [...]}
    tension_points: list[dict]
    # [{"topic": "...", "for_ratio": float, "against_ratio": float, "intensity": "...", "summary": "..."}]
    pain_points: list[dict]
    # [{"pain": "...", "severity": "...", "frequency": "...", "communities": [...], "verbatim": "..."}]
    sentiment_opportunities: list[dict]
    # [{"opportunity": "...", "based_on": "...", "confidence": "...", "target_audience": "..."}]


class SentimentAnalysisState(TypedDict):
    topic_name: str
    topic_description: str
    audience_name: str
    community_names: list[str]
    language: str

    # Populated by nodes
    relevant_posts: list[PostWithComments]
    sentiment_result: SentimentResult | None
