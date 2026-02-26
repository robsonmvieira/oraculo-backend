"""Agente LangGraph para extração de temas temporais (2 nós)."""

import json
import logging
import os

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.modules.shared.application.helpers.language_directive import (
    get_language_directive,
)
from app.modules.theme_analysis.application.use_cases.extract_themes_use_case.agent.prompts.theme_prompts import (
    get_extract_themes_prompt,
    get_generate_summary_prompt,
)
from app.modules.theme_analysis.application.use_cases.extract_themes_use_case.agent.state import (
    ExtractedTheme,
    ThemeExtractionState,
)

logger = logging.getLogger(__name__)

MAX_POSTS_CHARS = 80_000


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("MODEL_NAME", "gpt-5-nano-2025-08-07"),
        temperature=0,
    )


def _build_posts_text(posts: list[dict]) -> str:
    """Monta texto dos posts para injetar no prompt, respeitando limite de caracteres."""
    lines = []
    total_chars = 0
    for p in posts:
        line = f"[r/{p['subreddit']}] (score:{p['score']}, comments:{p['num_comments']}) {p['title']}"
        selftext = (p.get("selftext") or "")[:300]
        if selftext:
            line += f"\n  {selftext}"
        if p.get("permalink"):
            line += f"\n  permalink: {p['permalink']}"

        if total_chars + len(line) > MAX_POSTS_CHARS:
            break
        lines.append(line)
        total_chars += len(line)

    return "\n\n".join(lines)


def _calculate_engagement_score(theme: dict) -> float:
    """Calcula engagement score composto."""
    avg_score = theme.get("avg_score", 0) or 0
    avg_comments = theme.get("avg_comments", 0) or 0
    post_count = theme.get("post_count", 0) or 0
    subreddit_diversity = len(theme.get("top_subreddits", []))

    return (
        (avg_score * 0.4)
        + (avg_comments * 0.3)
        + (post_count * 0.2)
        + (subreddit_diversity * 0.1)
    )


def _parse_json_response(content: str) -> list[dict]:
    """Tenta extrair JSON array do conteúdo da resposta do LLM."""
    content = content.strip()
    # Remove markdown code fences se presente
    if content.startswith("```"):
        lines = content.split("\n")
        # Remove primeira e última linha (code fences)
        lines = [line for line in lines if not line.strip().startswith("```")]
        content = "\n".join(lines).strip()

    return json.loads(content)


def extract_themes(state: ThemeExtractionState) -> dict:
    """Nó 1: LLM identifica temas temporais a partir dos posts filtrados."""
    posts = state["posts"]
    if not posts:
        return {"extracted_themes": []}

    posts_text = _build_posts_text(posts)
    llm = _get_llm()
    language_directive = get_language_directive(state.get("language", "en"))

    communities_str = ", ".join(f"r/{c}" for c in state["community_names"])
    prompt = get_extract_themes_prompt(
        audience_name=state["audience_name"],
        communities_str=communities_str,
        time_window=state["time_window"],
        period_start=state["period_start"],
        period_end=state["period_end"],
        total_posts=state["total_posts"],
        posts_text=posts_text,
        language_directive=language_directive,
    )

    response = llm.invoke(prompt)

    try:
        raw_themes = _parse_json_response(response.content)
    except ValueError:
        logger.error("Failed to parse themes JSON from LLM response")
        return {"extracted_themes": []}

    themes: list[ExtractedTheme] = []
    for rank, raw in enumerate(raw_themes, start=1):
        theme = ExtractedTheme(
            name=raw.get("name", "Unknown Theme"),
            summary=None,  # Preenchido no nó 2
            post_count=raw.get("post_count", 0),
            avg_score=raw.get("avg_score", 0),
            avg_comments=raw.get("avg_comments", 0),
            engagement_score=_calculate_engagement_score(raw),
            top_subreddits=raw.get("top_subreddits", []),
            top_keywords=[
                {"keyword": kw, "frequency": 0} for kw in raw.get("keywords", [])
            ],
            representative_posts=raw.get("representative_posts", []),
            rank=rank,
        )
        themes.append(theme)

    # Re-rankear por engagement_score
    themes.sort(key=lambda t: t.get("engagement_score", 0) or 0, reverse=True)
    for i, theme in enumerate(themes, start=1):
        theme["rank"] = i

    logger.info("Extracted %d themes from %d posts", len(themes), len(posts))
    return {"extracted_themes": themes}


def generate_summary(state: ThemeExtractionState) -> dict:
    """Nó 2: LLM gera resumo narrativo para cada tema."""
    themes = state.get("extracted_themes", [])
    if not themes:
        return {"extracted_themes": themes}

    llm = _get_llm()
    language_directive = get_language_directive(state.get("language", "en"))
    communities_str = ", ".join(f"r/{c}" for c in state["community_names"])

    # Preparar JSON dos temas para o prompt
    themes_for_prompt = [
        {
            "name": t["name"],
            "post_count": t["post_count"],
            "avg_score": t["avg_score"],
            "avg_comments": t["avg_comments"],
            "top_subreddits": t["top_subreddits"],
            "top_keywords": t["top_keywords"],
        }
        for t in themes
    ]

    prompt = get_generate_summary_prompt(
        audience_name=state["audience_name"],
        communities_str=communities_str,
        time_window=state["time_window"],
        period_start=state["period_start"],
        period_end=state["period_end"],
        themes_json=json.dumps(themes_for_prompt, indent=2),
        language_directive=language_directive,
    )

    response = llm.invoke(prompt)

    try:
        summaries = _parse_json_response(response.content)
    except ValueError:
        logger.error("Failed to parse summaries JSON from LLM response")
        return {"extracted_themes": themes}

    # Mapear resumos aos temas por nome
    summary_map = {
        s["theme_name"]: s["summary"] for s in summaries if "theme_name" in s
    }
    for theme in themes:
        theme["summary"] = summary_map.get(theme["name"])

    logger.info("Generated summaries for %d themes", len(summary_map))
    return {"extracted_themes": themes}


def create_theme_extraction_agent():
    """Cria o agente LangGraph para extração de temas temporais."""
    workflow = StateGraph(ThemeExtractionState)

    workflow.add_node("extract_themes", extract_themes)
    workflow.add_node("generate_summary", generate_summary)

    workflow.add_edge(START, "extract_themes")
    workflow.add_edge("extract_themes", "generate_summary")
    workflow.add_edge("generate_summary", END)

    return workflow.compile()
