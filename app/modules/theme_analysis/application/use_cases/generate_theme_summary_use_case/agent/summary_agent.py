"""Agente LangGraph para geração de sumário narrativo enriquecido."""

import json
import logging
import os
import re

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.modules.theme_analysis.application.use_cases.generate_theme_summary_use_case.agent.prompts.summary_prompts import (
    build_intent_section,
    build_week_diff_instruction,
    get_generate_summary_prompt,
)
from app.modules.theme_analysis.application.use_cases.generate_theme_summary_use_case.agent.state import (
    SummaryResult,
    ThemeSummaryState,
)
from app.modules.shared.application.helpers.language_directive import (
    get_language_directive,
)

logger = logging.getLogger(__name__)

VALID_TONES = {
    "positive",
    "mixed",
    "tense",
    "neutral",
    "celebratory",
    "concerned",
    "supportive",
}


def _get_llm() -> ChatOpenAI:
    """Retorna instância do LLM configurada."""
    model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
    return ChatOpenAI(model=model_name, temperature=0)


def _parse_json_response(content: str) -> dict:
    """Extrai objeto JSON da resposta do LLM."""
    cleaned = content.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    try:
        result = json.loads(cleaned)
        if isinstance(result, dict):
            return result
        return {}
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM JSON response for theme summary")
        return {}


def generate_rich_summary(state: ThemeSummaryState) -> dict:
    """
    Nó único: Gera sumário narrativo enriquecido para um tema.

    Recebe dados do tema, posts representativos, métricas e opcionalmente
    dados de intenção (Theme 02). Retorna JSON estruturado com narrativa,
    highlights, tom emocional e sub-temas.
    """
    theme_data = state["theme_data"]
    language_directive = get_language_directive(state.get("language", "en"))
    communities_str = ", ".join(state.get("community_names", []))

    # Formatar top subreddits
    top_subs = theme_data.get("top_subreddits") or []
    top_subreddits_str = ", ".join(
        f"r/{s['name']} ({s.get('post_count', 0)} posts)" for s in top_subs[:5]
    )

    # Posts representativos formatados
    posts_text = state.get("posts_text", "No posts available.")

    # Seção de intenções (opcional)
    intent_breakdown = state.get("intent_breakdown")
    intent_section = ""
    if intent_breakdown:
        intent_section = build_intent_section(intent_breakdown)

    # Instrução de diferenciador temporal (opcional)
    previous_themes = state.get("previous_themes")
    week_diff_instruction = ""
    if previous_themes:
        week_diff_instruction = build_week_diff_instruction(
            state["time_window"], previous_themes
        )

    prompt = get_generate_summary_prompt(
        audience_name=state["audience_name"],
        time_window=state["time_window"],
        period_start=state["period_start"],
        period_end=state["period_end"],
        theme_name=theme_data["theme_name"],
        communities_str=communities_str,
        post_count=theme_data.get("post_count", 0),
        avg_score=theme_data.get("avg_score", 0),
        avg_comments=theme_data.get("avg_comments", 0),
        top_subreddits_str=top_subreddits_str,
        representative_posts_text=posts_text,
        intent_section=intent_section,
        week_diff_instruction=week_diff_instruction,
        language_directive=language_directive,
    )

    llm = _get_llm()
    response = llm.invoke(prompt)
    result = _parse_json_response(response.content)

    if not result:
        logger.error("Empty summary result from LLM for theme '%s'", theme_data["theme_name"])
        return {"summary_result": None}

    # Validar emotional_tone
    tone = result.get("emotional_tone", "neutral")
    if tone not in VALID_TONES:
        tone = "neutral"

    summary_result = SummaryResult(
        narrative=result.get("narrative", ""),
        highlights=result.get("highlights", []),
        emotional_tone=tone,
        tone_description=result.get("tone_description", ""),
        key_themes=result.get("key_themes", []),
        week_differentiator=result.get("week_differentiator"),
    )

    logger.info(
        "Generated rich summary for theme '%s': tone=%s, %d highlights, %d sub-themes",
        theme_data["theme_name"],
        tone,
        len(summary_result["highlights"]),
        len(summary_result["key_themes"]),
    )

    return {"summary_result": summary_result}


def create_theme_summary_agent():
    """Cria e compila o grafo LangGraph de geração de sumário narrativo."""
    workflow = StateGraph(ThemeSummaryState)
    workflow.add_node("generate_rich_summary", generate_rich_summary)
    workflow.add_edge(START, "generate_rich_summary")
    workflow.add_edge("generate_rich_summary", END)
    return workflow.compile()
