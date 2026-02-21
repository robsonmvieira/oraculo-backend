import logging
import os

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.modules.audience_keywords.application.use_cases.extract_keywords_use_case.agent.prompts.keyword_extraction_prompts import (
    extract_keywords_prompt,
)
from app.modules.audience_keywords.application.use_cases.extract_keywords_use_case.agent.state import (
    ExtractedKeyword,
    KeywordExtractionState,
)

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {"pain_point", "question", "recommendation", "trend", "general"}


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
        temperature=0.3,
    )


# ── Node 1: Extract keywords from community context ─────────────────────────


def extract_keywords(state: KeywordExtractionState) -> dict:
    """LLM generates search keywords based on audience community context."""
    llm = _get_llm()

    prompt = extract_keywords_prompt(
        audience_name=state["audience_name"],
        audience_description=state.get("audience_description"),
        community_names=state["community_names"],
        community_descriptions=state.get("community_descriptions", []),
        topics_summary=state.get("topics_summary"),
    )

    response = llm.invoke(prompt)

    keywords: list[ExtractedKeyword] = []
    rank = 1

    for line in response.content.strip().split("\n"):
        line = line.strip()
        if not line or "|" not in line:
            continue

        parts = line.split("|")
        if len(parts) < 3:
            continue

        keyword = parts[0].strip()
        category = parts[1].strip().lower()
        if category not in VALID_CATEGORIES:
            category = "general"

        try:
            relevance_score = int(parts[2].strip())
            relevance_score = max(1, min(10, relevance_score))
        except ValueError:
            relevance_score = 5

        keywords.append(
            ExtractedKeyword(
                keyword=keyword,
                category=category,
                relevance_score=relevance_score,
                rank=rank,
            )
        )
        rank += 1

    # Sort by relevance score (highest first) and re-rank
    keywords.sort(key=lambda k: k["relevance_score"], reverse=True)
    for i, kw in enumerate(keywords):
        kw["rank"] = i + 1

    logger.info("Extracted %d keywords for audience '%s'", len(keywords), state["audience_name"])
    return {"extracted_keywords": keywords}


# ── Graph assembly ───────────────────────────────────────────────────────────


def create_keyword_extraction_agent():
    """Create the LangGraph agent for keyword extraction."""
    workflow = StateGraph(KeywordExtractionState)

    workflow.add_node("extract_keywords", extract_keywords)

    workflow.add_edge(START, "extract_keywords")
    workflow.add_edge("extract_keywords", END)

    return workflow.compile()
