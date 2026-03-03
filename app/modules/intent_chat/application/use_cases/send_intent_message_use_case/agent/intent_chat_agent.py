import logging
import os

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.modules.shared.application.services.llm_factory import extract_response_text
from langgraph.graph import END, START, StateGraph

from app.modules.intent_chat.application.use_cases.send_intent_message_use_case.agent.prompts.intent_chat_prompts import (
    intent_chat_system_prompt,
)
from app.modules.intent_chat.application.use_cases.send_intent_message_use_case.agent.state import (
    IntentChatState,
)

logger = logging.getLogger(__name__)


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("MODEL_NAME", "gpt-5-nano-2025-08-07"),
        max_completion_tokens=16384,
    )


def build_context(state: IntentChatState) -> dict:
    """Validates context availability and determines quality."""
    intent_context = state.get("intent_context")

    if intent_context:
        logger.info(
            "Intent Chat: rich context available for category '%s'",
            state.get("intent_category"),
        )
        return {"context_quality": "rich"}

    logger.info(
        "Intent Chat: limited context for category '%s' (no analysis data)",
        state.get("intent_category"),
    )
    return {"context_quality": "limited"}


def answer_with_history(state: IntentChatState) -> dict:
    """LLM answers considering the full conversation history."""
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

    system_prompt = intent_chat_system_prompt(
        intent_category=state["intent_category"],
        audience_name=state["audience_name"],
        community_names=state.get("community_names", []),
        context_text=context_text,
        context_quality=context_quality,
        language=state.get("language", "en"),
    )

    # Build message list: system + conversation history
    langchain_messages = [SystemMessage(content=system_prompt)]

    for msg in state.get("messages", []):
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            langchain_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            langchain_messages.append(AIMessage(content=content))

    llm = _get_llm()

    logger.info(
        "Intent Chat: sending %d messages to LLM (model: %s)",
        len(langchain_messages),
        os.getenv("MODEL_NAME", "gpt-5-nano-2025-08-07"),
    )

    response = llm.invoke(langchain_messages)

    answer = extract_response_text(response) if response.content else ""

    if not answer:
        logger.warning(
            "Intent Chat: LLM returned empty answer for category '%s'. Full response: %s",
            state["intent_category"],
            repr(response),
        )

    logger.info(
        "Intent Chat: answered for category '%s' (quality: %s, length: %d chars)",
        state["intent_category"],
        context_quality,
        len(answer),
    )
    return {"answer": answer}


def create_intent_chat_agent():
    """Create the LangGraph agent for intent chat with conversation history."""
    workflow = StateGraph(IntentChatState)

    workflow.add_node("build_context", build_context)
    workflow.add_node("answer_with_history", answer_with_history)

    workflow.add_edge(START, "build_context")
    workflow.add_edge("build_context", "answer_with_history")
    workflow.add_edge("answer_with_history", END)

    return workflow.compile()
