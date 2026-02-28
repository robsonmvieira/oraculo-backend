import logging
import os

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.modules.shared.application.services.llm_factory import extract_response_text
from langgraph.graph import END, START, StateGraph

from app.modules.topic_chat.application.use_cases.send_message_use_case.agent.prompts.chat_prompts import (
    topic_chat_system_prompt,
)
from app.modules.topic_chat.application.use_cases.send_message_use_case.agent.state import (
    TopicChatState,
)

logger = logging.getLogger(__name__)


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("MODEL_NAME", "gpt-5-nano-2025-08-07"),
        max_completion_tokens=16384,
    )


def build_context(state: TopicChatState) -> dict:
    """Validates context availability and determines quality."""
    deep_dive_context = state.get("deep_dive_context")

    if deep_dive_context:
        logger.info(
            "Topic Chat: rich context available for topic '%s'",
            state.get("topic_name"),
        )
        return {"context_quality": "rich"}

    logger.info(
        "Topic Chat: limited context for topic '%s' (no deep dive)",
        state.get("topic_name"),
    )
    return {"context_quality": "limited"}


def answer_with_history(state: TopicChatState) -> dict:
    """LLM answers considering the full conversation history."""
    deep_dive_context = state.get("deep_dive_context")
    context_quality = state.get("context_quality", "limited")

    if deep_dive_context:
        context_text = deep_dive_context
    else:
        context_text = (
            f"Topic: {state['topic_name']}\n"
            f"Description: {state.get('topic_description', 'N/A')}\n"
            f"Communities: {', '.join(f'r/{c}' for c in state.get('community_names', []))}"
        )

    system_prompt = topic_chat_system_prompt(
        topic_name=state["topic_name"],
        topic_description=state.get("topic_description", ""),
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
        "Topic Chat: sending %d messages to LLM (model: %s)",
        len(langchain_messages),
        os.getenv("MODEL_NAME", "gpt-5-nano-2025-08-07"),
    )

    response = llm.invoke(langchain_messages)

    answer = extract_response_text(response) if response.content else ""

    if not answer:
        logger.warning(
            "Topic Chat: LLM returned empty answer for topic '%s'. Full response: %s",
            state["topic_name"],
            repr(response),
        )

    logger.info(
        "Topic Chat: answered for topic '%s' (quality: %s, length: %d chars)",
        state["topic_name"],
        context_quality,
        len(answer),
    )
    return {"answer": answer}


def create_chat_agent():
    """Create the LangGraph agent for topic chat with conversation history."""
    workflow = StateGraph(TopicChatState)

    workflow.add_node("build_context", build_context)
    workflow.add_node("answer_with_history", answer_with_history)

    workflow.add_edge(START, "build_context")
    workflow.add_edge("build_context", "answer_with_history")
    workflow.add_edge("answer_with_history", END)

    return workflow.compile()
