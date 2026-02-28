import logging
import os

from langchain_openai import ChatOpenAI

from app.modules.shared.application.services.llm_factory import extract_response_text
from langgraph.graph import END, START, StateGraph

from app.modules.topic_ask.application.use_cases.ask_topic_use_case.agent.prompts.ask_prompts import (
    topic_qa_prompt,
)
from app.modules.topic_ask.application.use_cases.ask_topic_use_case.agent.state import (
    TopicAskState,
)

logger = logging.getLogger(__name__)


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("MODEL_NAME", "gpt-5-nano-2025-08-07"),
        max_completion_tokens=16384,
    )


def build_context(state: TopicAskState) -> dict:
    """Validates context availability and determines quality."""
    deep_dive_context = state.get("deep_dive_context")

    if deep_dive_context:
        logger.info(
            "Ask Q&A: rich context available for topic '%s'",
            state.get("topic_name"),
        )
        return {"context_quality": "rich"}

    logger.info(
        "Ask Q&A: limited context for topic '%s' (no deep dive)",
        state.get("topic_name"),
    )
    return {"context_quality": "limited"}


def answer_question(state: TopicAskState) -> dict:
    """LLM answers the user question based on available context."""
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

    llm = _get_llm()
    prompt = topic_qa_prompt(
        topic_name=state["topic_name"],
        topic_description=state.get("topic_description", ""),
        audience_name=state["audience_name"],
        community_names=state.get("community_names", []),
        context_text=context_text,
        question=state["question"],
        context_quality=context_quality,
        language=state.get("language", "en"),
    )

    logger.info(
        "Ask Q&A: sending prompt to LLM (length: %d chars, model: %s)",
        len(prompt),
        os.getenv("MODEL_NAME", "gpt-5-nano-2025-08-07"),
    )

    response = llm.invoke(prompt)

    logger.info(
        "Ask Q&A: LLM response type=%s, content_length=%d, content_preview='%s'",
        type(response).__name__,
        len(response.content) if response.content else 0,
        (response.content[:200] if response.content else "<EMPTY>"),
    )

    answer = extract_response_text(response) if response.content else ""

    if not answer:
        logger.warning(
            "Ask Q&A: LLM returned empty answer for topic '%s'. Full response: %s",
            state["topic_name"],
            repr(response),
        )

    logger.info(
        "Ask Q&A: answered question for topic '%s' (quality: %s, length: %d chars)",
        state["topic_name"],
        context_quality,
        len(answer),
    )
    return {"answer": answer}


def create_ask_agent():
    """Create the LangGraph agent for topic Q&A."""
    workflow = StateGraph(TopicAskState)

    workflow.add_node("build_context", build_context)
    workflow.add_node("answer_question", answer_question)

    workflow.add_edge(START, "build_context")
    workflow.add_edge("build_context", "answer_question")
    workflow.add_edge("answer_question", END)

    return workflow.compile()
