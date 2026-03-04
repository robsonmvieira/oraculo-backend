import json
import logging

from langgraph.graph import END, START, StateGraph

from app.modules.semantic_search.application.use_cases.semantic_search_use_case.agent.prompts.semantic_search_prompts import (
    semantic_search_grouping_prompt,
    semantic_search_no_results_prompt,
)
from app.modules.semantic_search.application.use_cases.semantic_search_use_case.agent.state import (
    SemanticSearchState,
)
from app.modules.shared.application.services.llm_factory import (
    create_llm,
    extract_response_text,
)

logger = logging.getLogger(__name__)


def _build_posts_text(posts: list[dict]) -> str:
    """Build formatted text block from matched posts."""
    lines = []
    for p in posts:
        lines.append(
            f"POST_ID: {p['post_reddit_id']} | r/{p['subreddit']} | "
            f"Score: {p.get('score', 0)} | Comments: {p.get('num_comments', 0)} | "
            f"Similarity: {p.get('similarity', 0):.2f}"
        )
        lines.append(f"Title: {p['title']}")
        if p.get("selftext"):
            lines.append(f"Body: {p['selftext'][:500]}")
        lines.append("---")
    return "\n".join(lines)


def _parse_json_response(text: str) -> dict:
    """Parse JSON from LLM response, handling markdown code blocks."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return json.loads(text)


def analyze_and_group(state: SemanticSearchState) -> dict:
    """LLM analyzes matched posts and groups them into patterns."""
    matched_posts = state.get("matched_posts", [])
    llm = create_llm(temperature=0.3)

    if not matched_posts:
        prompt = semantic_search_no_results_prompt(
            audience_name=state["audience_name"],
            community_names=state.get("community_names", []),
            query=state["query"],
            language=state.get("language", "en"),
        )
        response = llm.invoke(prompt)
        answer = extract_response_text(response)
        return {
            "answer": answer,
            "patterns": [],
            "context_quality": "limited",
        }

    posts_text = _build_posts_text(matched_posts)

    prompt = semantic_search_grouping_prompt(
        audience_name=state["audience_name"],
        community_names=state.get("community_names", []),
        query=state["query"],
        posts_text=posts_text,
        total_matched=len(matched_posts),
        language=state.get("language", "en"),
    )

    logger.info(
        "Semantic search: sending %d posts to LLM for grouping (prompt: %d chars)",
        len(matched_posts),
        len(prompt),
    )

    response = llm.invoke(prompt)
    raw = extract_response_text(response)

    try:
        parsed = _parse_json_response(raw)
        summary = parsed.get("summary", "")
        raw_patterns = parsed.get("patterns", [])

        posts_map = {p["post_reddit_id"]: p for p in matched_posts}
        patterns = []
        for pattern in raw_patterns:
            submissions = []
            total_upvotes = 0
            total_comments = 0
            for pid in pattern.get("post_ids", []):
                fp = posts_map.get(pid)
                if not fp:
                    continue
                submissions.append(
                    {
                        "title": fp["title"],
                        "body": (fp.get("selftext") or "")[:500],
                        "subreddit": f"r/{fp['subreddit']}",
                        "score": fp.get("score", 0),
                        "num_comments": fp.get("num_comments", 0),
                        "permalink": fp.get("permalink", ""),
                        "similarity": fp.get("similarity", 0),
                    }
                )
                total_upvotes += fp.get("score", 0)
                total_comments += fp.get("num_comments", 0)

            if submissions:
                patterns.append(
                    {
                        "name": pattern.get("name", ""),
                        "emoji": pattern.get("emoji", ""),
                        "description": pattern.get("description", ""),
                        "post_count": len(submissions),
                        "total_upvotes": total_upvotes,
                        "total_comments": total_comments,
                        "submissions": submissions,
                    }
                )

        patterns.sort(key=lambda x: x["post_count"], reverse=True)

        logger.info(
            "Semantic search: %d patterns identified from %d posts",
            len(patterns),
            len(matched_posts),
        )

        return {
            "answer": summary,
            "patterns": patterns,
            "context_quality": "rich",
        }

    except (json.JSONDecodeError, KeyError):
        logger.exception("Failed to parse LLM grouping response")
        return {
            "answer": raw,
            "patterns": [],
            "context_quality": "limited",
        }


def create_semantic_search_agent():
    """Create the LangGraph agent for semantic search."""
    workflow = StateGraph(SemanticSearchState)

    workflow.add_node("analyze_and_group", analyze_and_group)

    workflow.add_edge(START, "analyze_and_group")
    workflow.add_edge("analyze_and_group", END)

    return workflow.compile()
