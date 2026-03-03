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
    sources = []
    if state.get("deep_dive_context"):
        sources.append("deep_dive")
    if state.get("sentiment_context"):
        sources.append("sentiment")
    if state.get("pattern_context"):
        sources.append("patterns")

    if len(sources) >= 2:
        quality = "rich"
    elif len(sources) == 1:
        quality = "partial"
    else:
        quality = "limited"

    logger.info(
        "Topic Chat: context quality '%s' for topic '%s' (sources: %s)",
        quality,
        state.get("topic_name"),
        sources,
    )
    return {"context_quality": quality}


def build_prompt_messages(
    topic_name: str,
    topic_description: str,
    audience_name: str,
    community_names: list[str],
    language: str,
    deep_dive_context: str | None,
    sentiment_context: str | None,
    pattern_context: str | None,
    context_quality: str,
    conversation_summary: str | None,
    messages: list[dict],
) -> list:
    """Build the LangChain message list for the LLM call.

    Shared between the synchronous agent node and the streaming path.
    """
    context_parts = []
    if deep_dive_context:
        context_parts.append(f"=== DEEP DIVE ANALYSIS ===\n{deep_dive_context}")
    if sentiment_context:
        context_parts.append(f"=== SENTIMENT ANALYSIS ===\n{sentiment_context}")
    if pattern_context:
        context_parts.append(f"=== PATTERN ANALYSIS ===\n{pattern_context}")

    if context_parts:
        context_text = "\n\n".join(context_parts)
    else:
        context_text = (
            f"Topic: {topic_name}\n"
            f"Description: {topic_description or 'N/A'}\n"
            f"Communities: {', '.join(f'r/{c}' for c in community_names)}"
        )

    system_prompt = topic_chat_system_prompt(
        topic_name=topic_name,
        topic_description=topic_description,
        audience_name=audience_name,
        community_names=community_names,
        context_text=context_text,
        context_quality=context_quality,
        language=language,
    )

    langchain_messages = [SystemMessage(content=system_prompt)]

    if conversation_summary:
        langchain_messages.append(
            SystemMessage(
                content=f"PREVIOUS CONVERSATION SUMMARY:\n{conversation_summary}"
            )
        )

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            langchain_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            langchain_messages.append(AIMessage(content=content))

    return langchain_messages


def answer_with_history(state: TopicChatState) -> dict:
    """LLM answers considering the full conversation history."""
    context_quality = state.get("context_quality", "limited")

    langchain_messages = build_prompt_messages(
        topic_name=state["topic_name"],
        topic_description=state.get("topic_description", ""),
        audience_name=state["audience_name"],
        community_names=state.get("community_names", []),
        language=state.get("language", "en"),
        deep_dive_context=state.get("deep_dive_context"),
        sentiment_context=state.get("sentiment_context"),
        pattern_context=state.get("pattern_context"),
        context_quality=context_quality,
        conversation_summary=state.get("conversation_summary"),
        messages=state.get("messages", []),
    )

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
