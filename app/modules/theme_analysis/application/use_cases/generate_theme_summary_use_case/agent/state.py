"""Estado do agente de geração de sumário narrativo."""

from typing import TypedDict


class ThemeData(TypedDict):
    """Dados do tema para geração do sumário."""

    theme_id: str
    theme_name: str
    summary: str | None
    post_count: int
    avg_score: float
    avg_comments: float
    top_subreddits: list[dict]  # [{"name": "...", "post_count": N, "avg_score": N}]
    top_keywords: list[dict]  # [{"keyword": "...", "frequency": N}]
    representative_posts: list[dict]  # [{"title": "...", "subreddit": "...", "score": N, "permalink": "..."}]


class SummaryResult(TypedDict):
    """Resultado da geração do sumário narrativo."""

    narrative: str
    highlights: list[dict]  # [{"title": "...", "subreddit": "...", "score": N, "why_notable": "..."}]
    emotional_tone: str
    tone_description: str
    key_themes: list[dict]  # [{"theme": "...", "description": "..."}]
    week_differentiator: str | None


class ThemeSummaryState(TypedDict):
    """Estado do grafo de geração de sumário narrativo."""

    # Inputs
    audience_name: str
    audience_description: str | None
    community_names: list[str]
    time_window: str
    period_start: str
    period_end: str
    language: str

    # Dados do tema
    theme_data: ThemeData
    posts_text: str  # Posts formatados para o prompt

    # Dados opcionais de intenções (Theme 02)
    intent_breakdown: dict | None  # {"advice_request": N, ...}

    # Dados históricos opcionais
    previous_themes: list[str] | None

    # Output
    summary_result: SummaryResult | None
