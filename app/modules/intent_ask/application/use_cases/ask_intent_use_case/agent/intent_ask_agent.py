import logging
import os

from langchain_openai import ChatOpenAI

from app.modules.shared.application.services.llm_factory import extract_response_text
from langgraph.graph import END, START, StateGraph

from app.modules.intent_ask.application.use_cases.ask_intent_use_case.agent.prompts.intent_ask_prompts import (
    intent_ask_prompt,
)
from app.modules.intent_ask.application.use_cases.ask_intent_use_case.agent.state import (
    IntentAskState,
)

logger = logging.getLogger(__name__)


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("MODEL_NAME", "gpt-5-nano-2025-08-07"),
        max_completion_tokens=16384,
    )


def build_context(state: IntentAskState) -> dict:
    """Validates context availability and determines quality."""
    intent_context = state.get("intent_context")

    if intent_context:
        logger.info(
            "Intent Ask: rich context available for category '%s'",
            state.get("intent_category"),
        )
        return {"context_quality": "rich"}

    logger.info(
        "Intent Ask: limited context for category '%s' (no analysis data)",
        state.get("intent_category"),
    )
    return {"context_quality": "limited"}


def answer_question(state: IntentAskState) -> dict:
    """LLM answers the user question based on available context."""
    intent_context = state.get("intent_context")
    context_quality = state.get("context_quality", "limited")

    if intent_context:
        context_text = intent_context
    else:
        context_text = (
            f"Intent Category: {state['intent_category']}\n"
            f"Audience: {state['audience_name']}\n"
            f"Communities: {', '.join(f'r/{c}' for c in state.get('community_names', []))}"
        )

    llm = _get_llm()
    prompt = intent_ask_prompt(
        intent_category=state["intent_category"],
        audience_name=state["audience_name"],
        community_names=state.get("community_names", []),
        context_text=context_text,
        question=state["question"],
        context_quality=context_quality,
        language=state.get("language", "en"),
    )

    logger.info(
        "Intent Ask: sending prompt to LLM (length: %d chars, model: %s)",
        len(prompt),
        os.getenv("MODEL_NAME", "gpt-5-nano-2025-08-07"),
    )

    response = llm.invoke(prompt)

    logger.info(
        "Intent Ask: LLM response type=%s, content_length=%d, content_preview='%s'",
        type(response).__name__,
        len(response.content) if response.content else 0,
        (response.content[:200] if response.content else "<EMPTY>"),
    )

    answer = extract_response_text(response) if response.content else ""

    if not answer:
        logger.warning(
            "Intent Ask: LLM returned empty answer for category '%s'. Full response: %s",
            state["intent_category"],
            repr(response),
        )

    logger.info(
        "Intent Ask: answered question for category '%s' (quality: %s, length: %d chars)",
        state["intent_category"],
        context_quality,
        len(answer),
    )
    return {"answer": answer}


def create_intent_ask_agent():
    """Create the LangGraph agent for intent Q&A."""
    workflow = StateGraph(IntentAskState)

    workflow.add_node("build_context", build_context)
    workflow.add_node("answer_question", answer_question)

    workflow.add_edge(START, "build_context")
    workflow.add_edge("build_context", "answer_question")
    workflow.add_edge("answer_question", END)

    return workflow.compile()
