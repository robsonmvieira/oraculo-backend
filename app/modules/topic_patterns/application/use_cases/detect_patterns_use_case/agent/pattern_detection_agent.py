import json
import logging
import os

from langgraph.graph import END, START, StateGraph

from app.modules.shared.application.services.llm_factory import (
    ContextLimits,
    create_llm,
    extract_response_text,
    get_context_limits,
)
from app.modules.topic_patterns.application.use_cases.detect_patterns_use_case.agent.prompts.pattern_detection_prompts import (
    pattern_detection_prompt,
)
from app.modules.topic_patterns.application.use_cases.detect_patterns_use_case.agent.state import (
    PatternDetectionState,
    PostWithComments,
    TopicSummary,
)

logger = logging.getLogger(__name__)

_MODEL_ENV = "PATTERN_DETECTION_MODEL_NAME"
_MODEL_FALLBACK_ENV = "MODEL_NAME"
_DEFAULT_MODEL = "gpt-5-nano-2025-08-07"

_OPENAI_OVERRIDES = {
    "max_posts_chars": 120_000,
    "max_comment_length": 500,
    "comments_per_post": 5,
    "max_selftext_length": 600,
    "top_posts_for_comments": 10,
    "comments_per_post_fetch": 20,
}


def _resolve_model_env() -> str:
    """Return the model name using the dedicated env var with fallback."""
    return os.getenv(_MODEL_ENV) or os.getenv(_MODEL_FALLBACK_ENV, _DEFAULT_MODEL)


def _get_llm():
    model = _resolve_model_env()
    return create_llm(model_env_var=_MODEL_ENV, default_model=model, temperature=0)


def _get_limits() -> ContextLimits:
    model = _resolve_model_env()
    return get_context_limits(
        model_env_var=_MODEL_ENV,
        default_model=model,
        openai_overrides=_OPENAI_OVERRIDES,
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
    limits: ContextLimits,
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

        if len(selftext) > limits.max_selftext_length:
            selftext = selftext[:limits.max_selftext_length] + "..."

        line = f"[r/{subreddit}] (score: {score}, comments: {num_comments}) {title}"
        if selftext:
            line += f"\n  {selftext}"

        comments = post.get("comments", [])
        if comments:
            line += "\n  --- Comments ---"
            for comment in comments[:limits.comments_per_post]:
                body = comment.get("body", "").strip()
                if len(body) > limits.max_comment_length:
                    body = body[:limits.max_comment_length] + "..."
                c_score = comment.get("score", 0)
                author = comment.get("author", "anonymous")
                line += f"\n  [{author}, score:{c_score}] {body}"

        if total_chars + len(line) > limits.max_posts_chars:
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

    limits = _get_limits()
    topics_text = _build_topics_text(topics)
    posts_text = _build_posts_with_comments_text(posts, limits)
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
    content = extract_response_text(response)

    # Clean markdown code blocks if present
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
    if content.endswith("```"):
        content = content[:-3].strip()

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        logger.error(
            "Failed to parse pattern detection JSON response: %s", content[:500]
        )
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
