import json
import logging
import os

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.modules.topic_deep_dive.application.use_cases.extract_deep_dive_use_case.agent.prompts.deep_dive_prompts import (
    deep_dive_analysis_prompt,
    select_representative_posts_prompt,
)
from app.modules.topic_deep_dive.application.use_cases.extract_deep_dive_use_case.agent.state import (
    DeepDiveState,
    PostWithComments,
)

logger = logging.getLogger(__name__)

MAX_POSTS_CHARS = 100_000  # Higher limit since we include comments
MAX_COMMENT_LENGTH = 500


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
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

        # Truncate long selftext
        if len(selftext) > 600:
            selftext = selftext[:600] + "..."

        line = f"[r/{subreddit}] (score: {score}, comments: {num_comments}) {title}"
        if selftext:
            line += f"\n  {selftext}"

        # Add top comments
        comments = post.get("comments", [])
        if comments:
            line += "\n  --- Comments ---"
            for comment in comments[:5]:  # Top 5 comments per post
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


def _build_posts_summary_text(posts: list[PostWithComments]) -> str:
    """Builds a summary text of posts for representative selection."""
    lines = []
    for post in posts:
        subreddit = post.get("subreddit", "")
        title = post.get("title", "").strip()
        score = post.get("score", 0)
        num_comments = post.get("num_comments", 0)
        permalink = post.get("permalink", "")
        selftext = post.get("selftext", "").strip()

        if len(selftext) > 200:
            selftext = selftext[:200] + "..."

        line = f"[r/{subreddit}] score:{score} comments:{num_comments} permalink:{permalink}\n  {title}"
        if selftext:
            line += f"\n  {selftext}"
        lines.append(line)

    return "\n\n".join(lines)


# ── Node 1: Analyze deep dive ──────────────────────────────────────────────


def analyze_deep_dive(state: DeepDiveState) -> dict:
    """LLM performs deep analysis of the topic from posts and comments."""
    posts = state.get("relevant_posts", [])
    if not posts:
        return {"deep_dive_result": None}

    posts_text = _build_posts_with_comments_text(posts)
    total_comments = sum(len(p.get("comments", [])) for p in posts)

    llm = _get_llm()
    prompt = deep_dive_analysis_prompt(
        topic_name=state["topic_name"],
        topic_description=state.get("topic_description", ""),
        audience_name=state["audience_name"],
        community_names=state["community_names"],
        posts_with_comments_text=posts_text,
        total_posts=len(posts),
        total_comments=total_comments,
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
        logger.error("Failed to parse deep dive JSON response: %s", content[:500])
        return {"deep_dive_result": None}

    logger.info("Deep dive analysis complete for topic '%s'", state["topic_name"])
    return {"deep_dive_result": result}


# ── Node 2: Extract representative posts ──────────────────────────────────


def extract_representative_posts(state: DeepDiveState) -> dict:
    """LLM selects representative posts for this topic."""
    result = state.get("deep_dive_result")
    posts = state.get("relevant_posts", [])

    if not result or not posts:
        return {}

    posts_text = _build_posts_summary_text(posts)
    llm = _get_llm()

    prompt = select_representative_posts_prompt(
        topic_name=state["topic_name"],
        posts_text=posts_text,
    )

    response = llm.invoke(prompt)
    content = response.content.strip()

    # Clean markdown code blocks if present
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
    if content.endswith("```"):
        content = content[:-3].strip()

    try:
        representative = json.loads(content)
        if isinstance(representative, list):
            result["representative_posts"] = representative
    except json.JSONDecodeError:
        logger.error("Failed to parse representative posts JSON: %s", content[:500])

    logger.info(
        "Selected %d representative posts for topic '%s'",
        len(result.get("representative_posts", [])),
        state["topic_name"],
    )
    return {"deep_dive_result": result}


# ── Graph assembly ──────────────────────────────────────────────────────────


def create_deep_dive_agent():
    """Create the LangGraph agent for topic deep dive analysis."""
    workflow = StateGraph(DeepDiveState)

    workflow.add_node("analyze_deep_dive", analyze_deep_dive)
    workflow.add_node("extract_representative_posts", extract_representative_posts)

    workflow.add_edge(START, "analyze_deep_dive")
    workflow.add_edge("analyze_deep_dive", "extract_representative_posts")
    workflow.add_edge("extract_representative_posts", END)

    return workflow.compile()
