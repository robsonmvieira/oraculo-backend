from typing import TypedDict


class TopicVideoData(TypedDict):
    """Dados coletados do YouTube para um tópico."""

    topic_name: str
    topic_description: str
    videos: list[dict]
    # Each video: {video_id, title, channel_name, views, likes, duration_seconds,
    #              tags, description, comments, transcript, transcript_lang, published_at}


class TopicRedditData(TypedDict):
    """Dados do Reddit para um tópico (existentes no sistema)."""

    topic_name: str
    topic_description: str
    post_count: int
    avg_score: float
    community_count: int
    communities: list[str]


class YouTubeValidationState(TypedDict):
    """Estado do grafo LangGraph para validação cross-platform."""

    # Input fields (set pelo caller em agent.invoke())
    audience_name: str
    language: str
    topics_reddit_data: list[TopicRedditData]
    topics_youtube_data: list[TopicVideoData]

    # Output fields (populated by nodes)
    analysis_result: dict | None  # Full cross-platform analysis
    analysis_summary: dict | None  # Executive summary
