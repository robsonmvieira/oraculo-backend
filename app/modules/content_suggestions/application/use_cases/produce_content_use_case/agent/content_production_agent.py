"""Agente LangGraph para producao de conteudo completo por plataforma."""

import json
import logging
import os

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.modules.shared.application.helpers.language_directive import (
    get_language_directive,
)
from app.modules.shared.application.services.llm_factory import extract_response_text

from .prompts.draft_prompts import get_draft_content_prompt
from .prompts.hooks_prompts import get_refine_hooks_prompt
from .state import ContentProductionState

logger = logging.getLogger(__name__)


def _get_llm() -> ChatOpenAI:
    """Retorna instancia do LLM para producao de conteudo."""
    model_name = os.getenv(
        "CONTENT_PRODUCTION_MODEL",
        os.getenv("MODEL_NAME", "gpt-5-nano-2025-08-07"),
    )
    return ChatOpenAI(model=model_name, temperature=0.5)


def _parse_json_response(text: str) -> list[dict]:
    """Extrai JSON array de uma resposta LLM."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = next((i for i, line in enumerate(lines) if line.strip().startswith("[")), 1)
        end = next(
            (i for i in range(len(lines) - 1, -1, -1) if lines[i].strip().startswith("]")),
            len(lines) - 2,
        )
        text = "\n".join(lines[start : end + 1])
    return json.loads(text)


def draft_content(state: ContentProductionState) -> dict:
    """No 1: Gera conteudo completo para cada plataforma alvo."""
    suggestion = state.get("suggestion", {})
    platforms = state.get("target_platforms", [])

    if not suggestion or not platforms:
        return {"platform_drafts": []}

    llm = _get_llm()
    language_directive = get_language_directive(state.get("language", "en"))
    communities_str = ", ".join(f"r/{c}" for c in state.get("community_names", []))

    prompt = get_draft_content_prompt(
        suggestion=suggestion,
        platforms=platforms,
        audience_name=state.get("audience_name", ""),
        communities_str=communities_str,
        language_directive=language_directive,
    )

    response = llm.invoke(prompt)
    try:
        drafts = _parse_json_response(extract_response_text(response))
    except (json.JSONDecodeError, ValueError):
        logger.error("Failed to parse content drafts JSON from LLM response")
        return {"platform_drafts": []}

    logger.info("Generated drafts for %d platforms", len(drafts))
    return {"platform_drafts": drafts}


def refine_and_hook(state: ContentProductionState) -> dict:
    """No 2: Refina drafts e garante qualidade dos hooks."""
    drafts = state.get("platform_drafts", [])
    suggestion = state.get("suggestion", {})

    if not drafts:
        return {"refined_drafts": []}

    llm = _get_llm()
    language_directive = get_language_directive(state.get("language", "en"))

    prompt = get_refine_hooks_prompt(
        drafts_json=json.dumps(drafts, indent=2, ensure_ascii=False),
        suggestion=suggestion,
        language_directive=language_directive,
    )

    response = llm.invoke(prompt)
    try:
        refined = _parse_json_response(extract_response_text(response))
    except (json.JSONDecodeError, ValueError):
        logger.error("Failed to parse refined drafts JSON, using original drafts")
        return {"refined_drafts": drafts}

    logger.info("Refined %d platform drafts", len(refined))
    return {"refined_drafts": refined}


def create_content_production_agent():
    """Cria o agente LangGraph para producao de conteudo (2 nos)."""
    workflow = StateGraph(ContentProductionState)

    workflow.add_node("draft_content", draft_content)
    workflow.add_node("refine_and_hook", refine_and_hook)

    workflow.add_edge(START, "draft_content")
    workflow.add_edge("draft_content", "refine_and_hook")
    workflow.add_edge("refine_and_hook", END)

    return workflow.compile()
