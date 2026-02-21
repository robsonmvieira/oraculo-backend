import logging
import os

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.modules.audience_topics.application.use_cases.extract_topics_use_case.agent.prompts.topic_extraction_prompts import (
    estimate_growth_prompt,
    extract_topics_prompt,
)
from app.modules.audience_topics.application.use_cases.extract_topics_use_case.agent.state import (
    ExtractedTopic,
    TopicExtractionState,
)

logger = logging.getLogger(__name__)

MAX_POSTS_CHARS = 80_000  # Limit to avoid exceeding context window


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
        temperature=0,
    )


def _build_posts_text(posts: list[dict], max_chars: int = MAX_POSTS_CHARS) -> str:
    """Builds a text block from posts, truncating to fit context window."""
    lines = []
    total_chars = 0

    for post in posts:
        title = post.get("title", "").strip()
        selftext = post.get("selftext", "").strip()
        subreddit = post.get("subreddit", "")

        # Truncate long selftext
        if len(selftext) > 300:
            selftext = selftext[:300] + "..."

        line = f"[r/{subreddit}] {title}"
        if selftext:
            line += f"\n  {selftext}"

        if total_chars + len(line) > max_chars:
            break

        lines.append(line)
        total_chars += len(line)

    return "\n\n".join(lines)


# ── Node 1: Extract topics from posts ───────────────────────────────────────


def extract_topics(state: TopicExtractionState) -> dict:
    """LLM extracts recurring topics from collected posts."""
    posts = state["posts"]
    if not posts:
        return {"extracted_topics": []}

    posts_text = _build_posts_text(posts)
    llm = _get_llm()

    prompt = extract_topics_prompt(
        audience_name=state["audience_name"],
        audience_description=state.get("audience_description"),
        community_names=state["community_names"],
        posts_text=posts_text,
        total_posts=state["total_posts"],
    )

    response = llm.invoke(prompt)

    topics: list[ExtractedTopic] = []
    rank = 1

    for line in response.content.strip().split("\n"):
        line = line.strip()
        if not line or "|" not in line:
            continue

        parts = line.split("|")
        if len(parts) < 6:
            continue

        name = parts[0].strip()
        description = parts[1].strip()

        try:
            mention_frequency = float(parts[2].strip())
        except ValueError:
            mention_frequency = None

        mention_period = parts[3].strip().lower()
        if mention_period not in ("day", "week", "month"):
            mention_period = "month"

        try:
            post_count = int(parts[4].strip())
        except ValueError:
            post_count = 0

        # Parse communities: "DogAdvice:10;CatAdvice:5"
        communities = []
        for comm_part in parts[5].strip().split(";"):
            comm_part = comm_part.strip()
            if ":" in comm_part:
                comm_name, comm_count = comm_part.rsplit(":", 1)
                try:
                    communities.append({
                        "name": comm_name.strip(),
                        "post_count": int(comm_count.strip()),
                    })
                except ValueError:
                    communities.append({"name": comm_name.strip(), "post_count": 0})

        topics.append(
            ExtractedTopic(
                name=name,
                description=description,
                growth_percentage=None,  # Filled in next node
                mention_frequency=mention_frequency,
                mention_period=mention_period,
                post_count=post_count,
                communities=communities,
                rank=rank,
            )
        )
        rank += 1

    logger.info("Extracted %d topics from %d posts", len(topics), len(posts))
    return {"extracted_topics": topics}


# ── Node 2: Estimate growth for each topic ───────────────────────────────────


def estimate_growth(state: TopicExtractionState) -> dict:
    """LLM estimates growth percentage for each extracted topic."""
    topics = state["extracted_topics"]
    if not topics:
        return {"extracted_topics": []}

    # Build topics summary for growth estimation
    topics_lines = []
    for t in topics:
        freq = f"{t['mention_frequency']}/{t['mention_period']}" if t["mention_frequency"] else "unknown"
        comm_count = len(t["communities"])
        topics_lines.append(
            f"{t['name']} — freq: {freq}, posts: {t['post_count']}, communities: {comm_count}"
        )

    topics_text = "\n".join(topics_lines)

    llm = _get_llm()
    prompt = estimate_growth_prompt(topics_text, state["audience_name"])
    response = llm.invoke(prompt)

    # Parse growth results
    growth_map = {}
    for line in response.content.strip().split("\n"):
        line = line.strip()
        if not line or "|" not in line:
            continue
        parts = line.split("|")
        if len(parts) >= 2:
            name = parts[0].strip()
            try:
                growth = float(parts[1].strip().replace("%", ""))
                growth_map[name.lower()] = growth
            except ValueError:
                continue

    # Apply growth to topics and re-rank by growth
    for topic in topics:
        growth = growth_map.get(topic["name"].lower())
        if growth is not None:
            topic["growth_percentage"] = growth

    # Re-rank by growth (highest first)
    topics.sort(
        key=lambda t: t.get("growth_percentage") or 0,
        reverse=True,
    )
    for i, topic in enumerate(topics):
        topic["rank"] = i + 1

    logger.info("Estimated growth for %d/%d topics", len(growth_map), len(topics))
    return {"extracted_topics": topics}


# ── Graph assembly ───────────────────────────────────────────────────────────


def create_topic_extraction_agent():
    """Create the LangGraph agent for topic extraction."""
    workflow = StateGraph(TopicExtractionState)

    workflow.add_node("extract_topics", extract_topics)
    workflow.add_node("estimate_growth", estimate_growth)

    workflow.add_edge(START, "extract_topics")
    workflow.add_edge("extract_topics", "estimate_growth")
    workflow.add_edge("estimate_growth", END)

    return workflow.compile()
