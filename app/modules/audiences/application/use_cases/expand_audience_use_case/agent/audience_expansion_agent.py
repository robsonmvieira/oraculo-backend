import logging
import os

from langchain_openai import ChatOpenAI

from app.modules.shared.application.services.llm_factory import extract_response_text
from langgraph.graph import END, START, StateGraph

from app.modules.audiences.application.use_cases.expand_audience_use_case.agent.prompts.audience_expansion_prompts import (
    analyze_audience_theme_prompt,
    rank_and_explain_prompt,
)
from app.modules.audiences.application.use_cases.expand_audience_use_case.agent.state import (
    AudienceExpansionState,
    RankedSuggestion,
)

logger = logging.getLogger(__name__)


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("MODEL_NAME", "gpt-5-nano-2025-08-07"),
        temperature=0,
    )


# ── Node 1: Analyze audience theme ──────────────────────────────────────────


def analyze_audience_theme(state: AudienceExpansionState) -> dict:
    """LLM analyzes all communities together to identify the audience theme."""
    communities = state["current_communities"]
    if not communities:
        return {"audience_theme": "General"}

    llm = _get_llm()
    prompt = analyze_audience_theme_prompt(
        communities, language=state.get("language", "en")
    )
    response = llm.invoke(prompt)

    theme = "General"

    for line in extract_response_text(response).split("\n"):
        if line.startswith("THEME:"):
            theme = line.replace("THEME:", "").strip()

    logger.info("Audience theme: %s", theme)

    # Only return theme — candidates are pre-collected by the use case
    return {"audience_theme": theme}


# ── Node 2: Filter and deduplicate ──────────────────────────────────────────


def filter_and_deduplicate(state: AudienceExpansionState) -> dict:
    """Remove duplicates and excluded communities."""
    excluded = {n.lower() for n in state["excluded_names"]}
    seen = set()
    filtered = []

    for candidate in state["candidates"]:
        name_lower = candidate["name"].lower()
        if name_lower in excluded or name_lower in seen:
            continue
        seen.add(name_lower)
        filtered.append(candidate)

    logger.info(
        "Filtered candidates: %d -> %d (excluded %d)",
        len(state["candidates"]),
        len(filtered),
        len(state["candidates"]) - len(filtered),
    )

    return {"candidates": filtered}


# ── Node 4: Rank and explain ────────────────────────────────────────────────


def rank_and_explain(state: AudienceExpansionState) -> dict:
    """LLM ranks candidates by relevance and generates a brief justification."""
    candidates = state["candidates"]
    if not candidates:
        return {"suggestions": []}

    # Only send candidates that have real data (not term_search placeholders)
    real_candidates = [c for c in candidates if c.get("subscribers") is not None]

    if not real_candidates:
        return {"suggestions": []}

    llm = _get_llm()
    prompt = rank_and_explain_prompt(
        state["audience_theme"], real_candidates, language=state.get("language", "en")
    )
    response = llm.invoke(prompt)

    # Build a lookup map from candidates
    candidate_map = {c["name"].lower(): c for c in real_candidates}

    suggestions: list[RankedSuggestion] = []
    for line in extract_response_text(response).split("\n"):
        line = line.strip()
        if not line or "|" not in line:
            continue

        parts = line.split("|")
        if len(parts) < 3:
            continue

        name = parts[0].strip().replace("r/", "")
        try:
            score = float(parts[1].strip())
        except ValueError:
            continue
        reason = parts[2].strip()

        candidate = candidate_map.get(name.lower())
        if not candidate:
            continue

        suggestions.append(
            RankedSuggestion(
                name=candidate["name"],
                title=candidate.get("title"),
                description=candidate.get("description"),
                subscribers=candidate.get("subscribers"),
                size_tag=None,  # Enriched by use case from community_stats
                activity_tag=None,  # Enriched by use case from community_stats
                growth_week=None,  # Enriched by use case from community_stats
                relevance_score=score,
                relevance_reason=reason,
            )
        )

    # Sort by score descending, limit to requested amount
    suggestions.sort(key=lambda s: s["relevance_score"], reverse=True)
    limit = state.get("limit", 10)
    suggestions = suggestions[:limit]

    logger.info("Ranked %d suggestions", len(suggestions))

    return {"suggestions": suggestions}


# ── Graph assembly ───────────────────────────────────────────────────────────


def create_audience_expansion_agent():
    """Create the LangGraph agent for audience expansion."""
    workflow = StateGraph(AudienceExpansionState)

    workflow.add_node("analyze_theme", analyze_audience_theme)
    workflow.add_node("filter", filter_and_deduplicate)
    workflow.add_node("rank", rank_and_explain)

    workflow.add_edge(START, "analyze_theme")
    workflow.add_edge("analyze_theme", "filter")
    workflow.add_edge("filter", "rank")
    workflow.add_edge("rank", END)

    return workflow.compile()
