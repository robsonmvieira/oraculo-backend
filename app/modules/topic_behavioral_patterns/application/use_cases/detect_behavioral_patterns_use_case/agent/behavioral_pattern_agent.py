import json
import logging

from langgraph.graph import END, START, StateGraph

from app.modules.shared.application.services.llm_factory import (
    ContextLimits,
    create_llm,
    get_context_limits,
)
from app.modules.topic_behavioral_patterns.application.use_cases.detect_behavioral_patterns_use_case.agent.prompts.behavioral_pattern_prompts import (
    behavioral_pattern_detection_prompt,
)
from app.modules.topic_behavioral_patterns.application.use_cases.detect_behavioral_patterns_use_case.agent.state import (
    BehavioralPatternState,
    PostWithComments,
)

logger = logging.getLogger(__name__)

_MODEL_ENV = "BEHAVIORAL_PATTERN_MODEL_NAME"
_DEFAULT_MODEL = "gpt-4o"

_OPENAI_OVERRIDES = {
    "max_posts_chars": 130_000,
    "max_comment_length": 600,
    "comments_per_post": 8,
    "max_selftext_length": 800,
    "top_posts_for_comments": 15,
    "comments_per_post_fetch": 35,
}


def _get_llm():
    return create_llm(model_env_var=_MODEL_ENV, default_model=_DEFAULT_MODEL, temperature=0)


def _get_limits() -> ContextLimits:
    return get_context_limits(
        model_env_var=_MODEL_ENV,
        default_model=_DEFAULT_MODEL,
        openai_overrides=_OPENAI_OVERRIDES,
    )


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


# ── Node 1: Detect behavioral patterns ──────────────────────────────────────


def detect_behavioral_patterns(state: BehavioralPatternState) -> dict:
    """LLM detects behavioral patterns from posts and comments."""
    posts = state.get("relevant_posts", [])
    if not posts:
        return {"pattern_result": None}

    limits = _get_limits()
    posts_text = _build_posts_with_comments_text(posts, limits)
    total_comments = sum(len(p.get("comments", [])) for p in posts)

    llm = _get_llm()
    prompt = behavioral_pattern_detection_prompt(
        topic_name=state["topic_name"],
        topic_description=state.get("topic_description", ""),
        audience_name=state["audience_name"],
        community_names=state["community_names"],
        posts_with_comments_text=posts_text,
        total_posts=len(posts),
        total_comments=total_comments,
        language=state.get("language", "en"),
    )

    response = llm.invoke(prompt)
    content = response.content.strip()

    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
    if content.endswith("```"):
        content = content[:-3].strip()

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        logger.error("Failed to parse behavioral pattern JSON response: %s", content[:500])
        return {"pattern_result": None}

    logger.info("Behavioral pattern analysis complete for topic '%s'", state["topic_name"])
    return {"pattern_result": result}


# ── Graph assembly ──────────────────────────────────────────────────────────


def create_behavioral_pattern_agent():
    """Create the LangGraph agent for topic behavioral pattern detection."""
    workflow = StateGraph(BehavioralPatternState)

    workflow.add_node("detect_behavioral_patterns", detect_behavioral_patterns)

    workflow.add_edge(START, "detect_behavioral_patterns")
    workflow.add_edge("detect_behavioral_patterns", END)

    return workflow.compile()
