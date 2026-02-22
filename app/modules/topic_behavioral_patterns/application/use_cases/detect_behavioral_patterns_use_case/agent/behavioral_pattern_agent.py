import json
import logging
import os

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.modules.topic_behavioral_patterns.application.use_cases.detect_behavioral_patterns_use_case.agent.prompts.behavioral_pattern_prompts import (
    behavioral_pattern_detection_prompt,
)
from app.modules.topic_behavioral_patterns.application.use_cases.detect_behavioral_patterns_use_case.agent.state import (
    BehavioralPatternState,
    PostWithComments,
)

logger = logging.getLogger(__name__)

MAX_POSTS_CHARS = 130_000
MAX_COMMENT_LENGTH = 600


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("BEHAVIORAL_PATTERN_MODEL_NAME", "gpt-4o"),
        temperature=0,
    )


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

        if len(selftext) > 800:
            selftext = selftext[:800] + "..."

        line = f"[r/{subreddit}] (score: {score}, comments: {num_comments}) {title}"
        if selftext:
            line += f"\n  {selftext}"

        comments = post.get("comments", [])
        if comments:
            line += "\n  --- Comments ---"
            for comment in comments[:8]:
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


# ── Node 1: Detect behavioral patterns ──────────────────────────────────────


def detect_behavioral_patterns(state: BehavioralPatternState) -> dict:
    """LLM detects behavioral patterns from posts and comments."""
    posts = state.get("relevant_posts", [])
    if not posts:
        return {"pattern_result": None}

    posts_text = _build_posts_with_comments_text(posts)
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
