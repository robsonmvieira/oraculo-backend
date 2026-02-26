"""Agente LangGraph para extração de subcategorias do painel de temas."""

import json
import logging
import os
import re

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.modules.theme_analysis.application.use_cases.generate_theme_panel_use_case.agent.prompts.panel_prompts import (
    get_extract_subcategories_prompt,
)
from app.modules.theme_analysis.application.use_cases.generate_theme_panel_use_case.agent.state import (
    SubcategoryItem,
    ThemePanelState,
)
from app.modules.shared.application.helpers.language_directive import (
    get_language_directive,
)

logger = logging.getLogger(__name__)


def _get_llm() -> ChatOpenAI:
    """Retorna instância do LLM configurada."""
    model_name = os.getenv("MODEL_NAME", "gpt-5-nano-2025-08-07")
    return ChatOpenAI(model=model_name, temperature=0)


def _parse_json_response(content: str) -> list[dict]:
    """Extrai array JSON da resposta do LLM."""
    cleaned = content.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    try:
        result = json.loads(cleaned)
        if isinstance(result, list):
            return result
        return []
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM JSON response for panel subcategories")
        return []


def extract_subcategories(state: ThemePanelState) -> dict:
    """
    Nó único: Extrai subcategorias temáticas/emocionais de um tema.

    Recebe posts do tema e retorna lista de subcategorias com contagens.
    """
    language_directive = get_language_directive(state.get("language", "en"))

    prompt = get_extract_subcategories_prompt(
        audience_name=state["audience_name"],
        theme_name=state["theme_name"],
        time_window=state["time_window"],
        period_start=state["period_start"],
        period_end=state["period_end"],
        posts_text=state.get("posts_text", "No posts available."),
        language_directive=language_directive,
    )

    llm = _get_llm()
    response = llm.invoke(prompt)
    items = _parse_json_response(response.content)

    if not items:
        logger.error(
            "Empty subcategories result from LLM for theme '%s'",
            state["theme_name"],
        )
        return {"subcategories": None}

    subcategories = [
        SubcategoryItem(
            name=item.get("name", ""),
            count=item.get("count", 0),
            description=item.get("description", ""),
        )
        for item in items
        if item.get("name")
    ]

    # Ordenar por count desc
    subcategories.sort(key=lambda x: x["count"], reverse=True)

    logger.info(
        "Extracted %d subcategories for theme '%s'",
        len(subcategories),
        state["theme_name"],
    )

    return {"subcategories": subcategories}


def create_theme_panel_agent():
    """Cria e compila o grafo LangGraph de extração de subcategorias."""
    workflow = StateGraph(ThemePanelState)
    workflow.add_node("extract_subcategories", extract_subcategories)
    workflow.add_edge(START, "extract_subcategories")
    workflow.add_edge("extract_subcategories", END)
    return workflow.compile()
