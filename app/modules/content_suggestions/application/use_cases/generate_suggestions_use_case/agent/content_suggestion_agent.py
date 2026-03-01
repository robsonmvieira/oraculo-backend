"""Agente LangGraph para geração de sugestões inteligentes de conteúdo (5 nós)."""

import json
import logging
import os

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.modules.shared.application.helpers.language_directive import (
    get_language_directive,
)
from app.modules.shared.application.services.llm_factory import extract_response_text
from app.modules.content_suggestions.application.use_cases.generate_suggestions_use_case.agent.prompts.accuracy_prompts import (
    get_accuracy_review_prompt,
)
from app.modules.content_suggestions.application.use_cases.generate_suggestions_use_case.agent.prompts.differentiation_prompts import (
    get_differentiation_prompt,
)
from app.modules.content_suggestions.application.use_cases.generate_suggestions_use_case.agent.prompts.opportunity_prompts import (
    get_rank_opportunities_prompt,
)
from app.modules.content_suggestions.application.use_cases.generate_suggestions_use_case.agent.prompts.strategy_prompts import (
    get_content_strategy_prompt,
)
from app.modules.content_suggestions.application.use_cases.generate_suggestions_use_case.agent.state import (
    ContentSuggestionState,
)

logger = logging.getLogger(__name__)


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("CONTENT_SUGGESTION_MODEL", os.getenv("MODEL_NAME", "gpt-5-nano-2025-08-07")),
        temperature=0.3,
    )


def _parse_json_response(content: str) -> list[dict]:
    """Extrai JSON array da resposta do LLM."""
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        content = "\n".join(lines).strip()
    return json.loads(content)


def assemble_context(state: ContentSuggestionState) -> dict:
    """Nó 1: O contexto já foi montado pelo context_builder. Passa direto."""
    logger.info(
        "Context assembled: %d modules available, %d topic contexts, %d chars",
        len(state.get("modules_available", [])),
        len(state.get("topic_contexts", [])),
        len(state.get("assembled_context", "")),
    )
    return {}


def rank_opportunities(state: ContentSuggestionState) -> dict:
    """Nó 2: Cruza sinais e rankeia oportunidades de conteúdo."""
    assembled_context = state.get("assembled_context", "")
    if not assembled_context:
        return {"ranked_opportunities": []}

    llm = _get_llm()
    language_directive = get_language_directive(state.get("language", "en"))
    communities_str = ", ".join(f"r/{c}" for c in state["community_names"])

    prompt = get_rank_opportunities_prompt(
        audience_name=state["audience_name"],
        community_names_str=communities_str,
        assembled_context=assembled_context,
        language_directive=language_directive,
    )

    response = llm.invoke(prompt)
    try:
        opportunities = _parse_json_response(extract_response_text(response))
    except (json.JSONDecodeError, ValueError):
        logger.error("Failed to parse opportunities JSON from LLM response")
        return {"ranked_opportunities": []}

    opportunities.sort(key=lambda x: x.get("score", 0), reverse=True)
    logger.info("Ranked %d content opportunities", len(opportunities))
    return {"ranked_opportunities": opportunities}


def generate_strategies(state: ContentSuggestionState) -> dict:
    """Nó 3: Gera sugestões detalhadas para as top oportunidades."""
    opportunities = state.get("ranked_opportunities", [])
    if not opportunities:
        return {"content_suggestions": []}

    llm = _get_llm()
    language_directive = get_language_directive(state.get("language", "en"))
    communities_str = ", ".join(f"r/{c}" for c in state["community_names"])

    prompt = get_content_strategy_prompt(
        audience_name=state["audience_name"],
        community_names_str=communities_str,
        assembled_context=state.get("assembled_context", ""),
        opportunities_json=json.dumps(opportunities[:5], indent=2),
        language_directive=language_directive,
    )

    response = llm.invoke(prompt)
    try:
        suggestions = _parse_json_response(extract_response_text(response))
    except (json.JSONDecodeError, ValueError):
        logger.error("Failed to parse content strategies JSON from LLM response")
        return {"content_suggestions": []}

    logger.info("Generated %d content suggestions", len(suggestions))
    return {"content_suggestions": suggestions}


def check_differentiation(state: ContentSuggestionState) -> dict:
    """Nó 4: Valida diferenciação e refina sugestões."""
    suggestions = state.get("content_suggestions", [])
    if not suggestions:
        return {"differentiated_suggestions": []}

    llm = _get_llm()
    language_directive = get_language_directive(state.get("language", "en"))

    prompt = get_differentiation_prompt(
        audience_name=state["audience_name"],
        suggestions_json=json.dumps(suggestions, indent=2),
        assembled_context=state.get("assembled_context", ""),
        language_directive=language_directive,
    )

    response = llm.invoke(prompt)
    try:
        differentiated = _parse_json_response(extract_response_text(response))
    except (json.JSONDecodeError, ValueError):
        logger.error("Failed to parse differentiation JSON from LLM response")
        return {"differentiated_suggestions": suggestions}

    logger.info("Differentiation check complete: %d suggestions", len(differentiated))
    return {"differentiated_suggestions": differentiated}


def review_accuracy(state: ContentSuggestionState) -> dict:
    """Nó 5: Cruza sugestões com contexto original e valida acurácia."""
    suggestions = state.get("differentiated_suggestions", [])
    if not suggestions:
        return {"verified_suggestions": []}

    llm = _get_llm()
    language_directive = get_language_directive(state.get("language", "en"))

    prompt = get_accuracy_review_prompt(
        suggestions_json=json.dumps(suggestions, indent=2),
        assembled_context=state.get("assembled_context", ""),
        language_directive=language_directive,
    )

    response = llm.invoke(prompt)
    try:
        verified = _parse_json_response(extract_response_text(response))
    except (json.JSONDecodeError, ValueError):
        logger.error("Failed to parse accuracy review JSON from LLM response")
        return {"verified_suggestions": suggestions}

    logger.info("Accuracy review complete: %d verified suggestions", len(verified))
    return {"verified_suggestions": verified}


def create_content_suggestion_agent():
    """Cria o agente LangGraph para sugestões de conteúdo (5 nós)."""
    workflow = StateGraph(ContentSuggestionState)

    workflow.add_node("assemble_context", assemble_context)
    workflow.add_node("rank_opportunities", rank_opportunities)
    workflow.add_node("generate_strategies", generate_strategies)
    workflow.add_node("check_differentiation", check_differentiation)
    workflow.add_node("review_accuracy", review_accuracy)

    workflow.add_edge(START, "assemble_context")
    workflow.add_edge("assemble_context", "rank_opportunities")
    workflow.add_edge("rank_opportunities", "generate_strategies")
    workflow.add_edge("generate_strategies", "check_differentiation")
    workflow.add_edge("check_differentiation", "review_accuracy")
    workflow.add_edge("review_accuracy", END)

    return workflow.compile()
