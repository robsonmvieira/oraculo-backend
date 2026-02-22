from typing import TypedDict


class ExtractedKeyword(TypedDict):
    keyword: str
    category: str | None  # pain_point, question, recommendation, trend, general
    relevance_score: int  # 1-10
    rank: int


class KeywordExtractionState(TypedDict):
    audience_name: str
    audience_description: str | None
    community_names: list[str]
    community_descriptions: list[str]
    topics_summary: str | None
    language: str

    # Populated by nodes
    extracted_keywords: list[ExtractedKeyword]
