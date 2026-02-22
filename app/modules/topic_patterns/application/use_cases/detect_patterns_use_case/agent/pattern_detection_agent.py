import json
import logging
import os

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.modules.topic_patterns.application.use_cases.detect_patterns_use_case.agent.prompts.pattern_detection_prompts import (
    pattern_detection_prompt,
)
from app.modules.topic_patterns.application.use_cases.detect_patterns_use_case.agent.state import (
    PatternDetectionState,
    PostWithComments,
    TopicSummary,
)

logger = logging.getLogger(__name__)

MAX_POSTS_CHARS = 120_000  # Higher limit — cross-topic needs more context
MAX_COMMENT_LENGTH = 500


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
        temperature=0,
    )


def _build_topics_text(topics: list[TopicSummary]) -> str:
    """Builds a text block summarizing all topics."""
    lines = []
    for t in topics:
        communities = ", ".join(t.get("communities", []))
        freq = t.get("estimated_frequency", "unknown")
        growth = t.get("growth_trend", "unknown")
        desc = t.get("description", "")
        line = f"- {t['name']} (frequency: {freq}, growth: {growth})"
        if communities:
            line += f"\n  Communities: {communities}"
        if desc:
            line += f"\n  {desc}"
        lines.append(line)
    return "\n".join(lines)


def _build_posts_with_comments_text(
    posts: list[PostWithComments],
    max_chars: int = MAX_POSTS_CHARS,
) -> str:
    """Builds a text block from posts with their comments."""
    lines = []
    total_chars = 0

    for post in posts:
        subreddit = post.get("subreddit", "")
        title = post.get("title", "").strip()
        selftext = post.get("selftext", "").strip()
        score = post.get("score", 0)
        num_comments = post.get("num_comments", 0)

        if len(selftext) > 600:
            selftext = selftext[:600] + "..."

        line = f"[r/{subreddit}] (score: {score}, comments: {num_comments}) {title}"
        if selftext:
            line += f"\n  {selftext}"

        comments = post.get("comments", [])
        if comments:
            line += "\n  --- Comments ---"
            for comment in comments[:5]:
                body = comment.get("body", "").strip()
                if len(body) > MAX_COMMENT_LENGTH:
                    body = body[:MAX_COMMENT_LENGTH] + "..."
                c_score = comment.get("score", 0)
                author = comment.get("author", "anonymous")
                line += f"\n  [{author}, score:{c_score}] {body}"

        if total_chars + len(line) > max_chars:
            break

        lines.append(line)
        total_chars += len(line)

    return "\n\n".join(lines)


# -- Node 1: Collect context (no-op, data already prepared by use case) -----


def collect_context(state: PatternDetectionState) -> dict:
    """Validates that the state has the data needed for pattern detection."""
    topics = state.get("topics", [])
    posts = state.get("posts_with_comments", [])

    logger.info(
        "Pattern detection context: %d topics, %d posts",
        len(topics),
        len(posts),
    )

    if not topics:
        return {"pattern_result": None}

    return {}


# -- Node 2: Detect patterns via LLM ----------------------------------------


def detect_patterns(state: PatternDetectionState) -> dict:
    """LLM analyzes all topics and posts to detect cross-topic patterns."""
    topics = state.get("topics", [])
    posts = state.get("posts_with_comments", [])

    if not topics:
        return {"pattern_result": None}

    topics_text = _build_topics_text(topics)
    posts_text = _build_posts_with_comments_text(posts)
    total_comments = sum(len(p.get("comments", [])) for p in posts)

    llm = _get_llm()
    prompt = pattern_detection_prompt(
        audience_name=state["audience_name"],
        community_names=state["community_names"],
        topics_text=topics_text,
        posts_with_comments_text=posts_text,
        total_topics=len(topics),
        total_posts=len(posts),
        total_comments=total_comments,
        language=state.get("language", "en"),
    )

    response = llm.invoke(prompt)
    content = response.content.strip()

    # Clean markdown code blocks if present
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
    if content.endswith("```"):
        content = content[:-3].strip()

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        logger.error("Failed to parse pattern detection JSON response: %s", content[:500])
        return {"pattern_result": None}

    logger.info(
        "Pattern detection complete: %d co-occurrences, %d opportunities",
        len(result.get("co_occurrences", [])),
        len(result.get("content_opportunities", [])),
    )
    return {"pattern_result": result}


# -- Graph assembly ----------------------------------------------------------


def create_pattern_detection_agent():
    """Create the LangGraph agent for cross-topic pattern detection."""
    workflow = StateGraph(PatternDetectionState)

    workflow.add_node("collect_context", collect_context)
    workflow.add_node("detect_patterns", detect_patterns)

    workflow.add_edge(START, "collect_context")
    workflow.add_edge("collect_context", "detect_patterns")
    workflow.add_edge("detect_patterns", END)

    return workflow.compile()
