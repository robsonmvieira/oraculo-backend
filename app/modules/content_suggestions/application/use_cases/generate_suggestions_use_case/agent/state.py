"""Estado do agente de sugestões inteligentes de conteúdo."""

from typing import TypedDict


class TopicContext(TypedDict):
    topic_id: str
    topic_name: str
    growth_percentage: float | None
    mention_frequency: float
    post_count: int
    communities: list[str]


class OpportunityScore(TypedDict):
    title: str
    score: float
    justification: str
    source_topics: list[str]
    signals: list[str]


class ContentSuggestionResult(TypedDict):
    rank: int
    priority: str
    title: str
    approach: str
    why_now: str
    evidence: dict
    format: str
    format_rationale: str
    emotional_tone: str
    tone_rationale: str
    outline: list[dict]
    keywords: list[str]
    research_notes: str
    image_prompt: str
    differentiation_notes: str
    accuracy_notes: str
    source_topics: list[dict]
    source_modules: list[str]


class ContentSuggestionState(TypedDict):
    # Inputs
    audience_id: str
    audience_name: str
    audience_description: str | None
    community_names: list[str]
    language: str

    # Assembled context (Node 1)
    assembled_context: str
    modules_available: list[str]
    topic_contexts: list[TopicContext]

    # Ranked opportunities (Node 2)
    ranked_opportunities: list[OpportunityScore]

    # Content suggestions (Node 3)
    content_suggestions: list[ContentSuggestionResult]

    # Differentiated suggestions (Node 4)
    differentiated_suggestions: list[ContentSuggestionResult]

    # Final verified output (Node 5)
    verified_suggestions: list[ContentSuggestionResult]
