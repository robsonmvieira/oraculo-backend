import json
import logging
import os

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.modules.topic_sentiment.application.use_cases.extract_sentiment_use_case.agent.prompts.sentiment_prompts import (
    sentiment_analysis_prompt,
)
from app.modules.topic_sentiment.application.use_cases.extract_sentiment_use_case.agent.state import (
    PostWithComments,
    SentimentAnalysisState,
)

logger = logging.getLogger(__name__)

MAX_POSTS_CHARS = 100_000
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


# ── Node 1: Collect context ─────────────────────────────────────────────────


def collect_context(state: SentimentAnalysisState) -> dict:
    """Validates that we have posts to analyze."""
    posts = state.get("relevant_posts", [])
    if not posts:
        logger.warning("No posts available for sentiment analysis of '%s'", state.get("topic_name"))
        return {"sentiment_result": None}

    logger.info(
        "Sentiment analysis: %d posts ready for topic '%s'",
        len(posts),
        state.get("topic_name"),
    )
    return {}


# ── Node 2: Analyze sentiment ───────────────────────────────────────────────


def analyze_sentiment(state: SentimentAnalysisState) -> dict:
    """LLM performs deep sentiment analysis of the topic from posts and comments."""
    if state.get("sentiment_result") is None and not state.get("relevant_posts"):
        return {"sentiment_result": None}

    posts = state.get("relevant_posts", [])
    posts_text = _build_posts_with_comments_text(posts)
    total_comments = sum(len(p.get("comments", [])) for p in posts)

    llm = _get_llm()
    prompt = sentiment_analysis_prompt(
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

    # Clean markdown code blocks if present
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
    if content.endswith("```"):
        content = content[:-3].strip()

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        logger.error("Failed to parse sentiment JSON response: %s", content[:500])
        return {"sentiment_result": None}

    logger.info(
        "Sentiment analysis complete for topic '%s': %d emotions, %d pain points, %d opportunities",
        state["topic_name"],
        len(result.get("emotional_map", [])),
        len(result.get("pain_points", [])),
        len(result.get("sentiment_opportunities", [])),
    )
    return {"sentiment_result": result}


# ── Graph assembly ───────────────────────────────────────────────────────────


def create_sentiment_agent():
    """Create the LangGraph agent for topic sentiment analysis."""
    workflow = StateGraph(SentimentAnalysisState)

    workflow.add_node("collect_context", collect_context)
    workflow.add_node("analyze_sentiment", analyze_sentiment)

    workflow.add_edge(START, "collect_context")
    workflow.add_edge("collect_context", "analyze_sentiment")
    workflow.add_edge("analyze_sentiment", END)

    return workflow.compile()
