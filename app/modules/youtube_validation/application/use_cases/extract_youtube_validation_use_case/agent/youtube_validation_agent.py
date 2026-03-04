"""LangGraph agent for cross-platform YouTube validation.

Graph: START → analyze_cross_platform → generate_summary → END

Routes to unified (Gemini) or per-topic (OpenAI) analysis based on
the configured model's provider.
"""

import json
import logging
import os

from langgraph.graph import END, START, StateGraph

from app.modules.shared.application.services.llm_factory import (
    create_llm,
    extract_response_text,
)
from app.modules.youtube_validation.application.helpers.youtube_context_limits import (
    get_youtube_context_limits,
)
from app.modules.youtube_validation.application.use_cases.extract_youtube_validation_use_case.agent.prompts.youtube_validation_prompts import (
    per_topic_validation_prompt,
    summary_prompt,
    unified_validation_prompt,
)
from app.modules.youtube_validation.application.use_cases.extract_youtube_validation_use_case.agent.state import (
    YouTubeValidationState,
)

logger = logging.getLogger(__name__)

_MODEL_ENV = "YOUTUBE_VALIDATION_MODEL_NAME"
_MODEL_FALLBACK_ENV = "MODEL_NAME"
_DEFAULT_MODEL = "gpt-5-nano-2025-08-07"


def _resolve_model_env() -> str:
    """Return the model name using the dedicated env var with fallback."""
    return os.getenv(_MODEL_ENV) or os.getenv(_MODEL_FALLBACK_ENV, _DEFAULT_MODEL)


def _get_llm():
    model = _resolve_model_env()
    return create_llm(model_env_var=_MODEL_ENV, default_model=model, temperature=0)


def _parse_json_response(content: str) -> dict | None:
    """Parse JSON from LLM response, cleaning markdown code blocks."""
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON response: %s", text[:500])
        return None


# ── Text builders ──────────────────────────────────────────────────────────


def _build_topic_text(
    reddit_data: dict,
    youtube_data: dict,
    max_comments: int = 100,
    max_transcript_chars: int = 50_000,
) -> str:
    """Constrói texto de um tópico com dados Reddit + YouTube."""
    lines = []
    topic_name = reddit_data.get("topic_name", youtube_data.get("topic_name", ""))

    lines.append(f"=== TOPIC: {topic_name} ===")

    # Reddit section
    lines.append("\n--- REDDIT DATA ---")
    lines.append(f"Description: {reddit_data.get('topic_description', 'N/A')}")
    lines.append(f"Post count: {reddit_data.get('post_count', 0)}")
    lines.append(f"Average score: {reddit_data.get('avg_score', 0)}")
    lines.append(
        f"Communities ({reddit_data.get('community_count', 0)}): "
        f"{', '.join(reddit_data.get('communities', []))}"
    )

    # YouTube section
    videos = youtube_data.get("videos", [])
    lines.append(f"\n--- YOUTUBE DATA ({len(videos)} videos) ---")

    total_transcript_chars = 0
    for v in videos:
        title = v.get("title", "")
        views = v.get("views", "N/A")
        likes = v.get("likes", "N/A")
        duration = v.get("duration_seconds", "N/A")
        channel = v.get("channel_name", "N/A")

        lines.append(
            f"\n[VIDEO] {title}\n"
            f"  Channel: {channel} | Views: {views} | Likes: {likes} | Duration: {duration}s"
        )

        # Video description (truncate)
        desc = v.get("description", "")
        if desc:
            if len(desc) > 500:
                desc = desc[:500] + "..."
            lines.append(f"  Description: {desc}")

        # Comments
        comments = v.get("comments", [])
        if comments:
            lines.append(f"  Comments ({len(comments)}):")
            for c in comments[:max_comments]:
                text = c.get("text", "")
                if len(text) > 300:
                    text = text[:300] + "..."
                lines.append(
                    f"    [{c.get('author', '?')}, likes:{c.get('likes', 0)}] {text}"
                )

        # Transcript
        transcript = v.get("transcript", "")
        if transcript and total_transcript_chars < max_transcript_chars:
            remaining = max_transcript_chars - total_transcript_chars
            if len(transcript) > remaining:
                transcript = transcript[:remaining] + "..."
            lines.append(
                f"  Transcript ({v.get('transcript_lang', '?')}): {transcript}"
            )
            total_transcript_chars += len(transcript)

    return "\n".join(lines)


def _build_all_topics_text(
    reddit_data_list: list[dict],
    youtube_data_list: list[dict],
    limits,
) -> str:
    """Constrói texto completo de todos os tópicos para análise unificada."""
    sections = []
    total_chars = 0

    # Cria mapa de youtube_data por topic_name
    yt_map = {d["topic_name"]: d for d in youtube_data_list}

    for reddit in reddit_data_list:
        topic_name = reddit.get("topic_name", "")
        yt = yt_map.get(topic_name, {"topic_name": topic_name, "videos": []})

        section = _build_topic_text(
            reddit,
            yt,
            max_comments=limits.max_comments_per_video,
            max_transcript_chars=limits.max_transcript_chars,
        )

        if total_chars + len(section) > limits.max_total_analysis_chars:
            logger.warning("Truncating topics text at %d chars", total_chars)
            break

        sections.append(section)
        total_chars += len(section)

    return "\n\n" + "=" * 60 + "\n\n".join(sections)


# ── Node 1: Cross-platform analysis ───────────────────────────────────────


def analyze_cross_platform(state: YouTubeValidationState) -> dict:
    """Nó principal: roteia para unified ou per_topic baseado no provider."""
    limits = get_youtube_context_limits()

    reddit_data = state.get("topics_reddit_data", [])
    youtube_data = state.get("topics_youtube_data", [])

    if not reddit_data and not youtube_data:
        return {"analysis_result": None}

    if limits.analysis_mode == "unified":
        return _unified_analysis(state, limits)
    else:
        return _per_topic_analysis(state, limits)


def _unified_analysis(state: YouTubeValidationState, limits) -> dict:
    """Gemini path: todos os tópicos em 1 chamada LLM."""
    reddit_data = state.get("topics_reddit_data", [])
    youtube_data = state.get("topics_youtube_data", [])

    topics_text = _build_all_topics_text(reddit_data, youtube_data, limits)
    total_videos = sum(len(d.get("videos", [])) for d in youtube_data)
    total_comments = sum(
        sum(len(v.get("comments", [])) for v in d.get("videos", []))
        for d in youtube_data
    )

    llm = _get_llm()
    prompt = unified_validation_prompt(
        audience_name=state["audience_name"],
        topics_text=topics_text,
        total_topics=len(reddit_data),
        total_videos=total_videos,
        total_comments=total_comments,
        language=state.get("language", "en"),
    )

    response = llm.invoke(prompt)
    content = extract_response_text(response)
    result = _parse_json_response(content)

    if not result:
        return {"analysis_result": None}

    logger.info(
        "Unified cross-platform analysis complete for %d topics", len(reddit_data)
    )
    return {"analysis_result": result}


def _per_topic_analysis(state: YouTubeValidationState, limits) -> dict:
    """OpenAI path: 1 chamada LLM por tópico, depois agrega."""
    reddit_data = state.get("topics_reddit_data", [])
    youtube_data = state.get("topics_youtube_data", [])

    yt_map = {d["topic_name"]: d for d in youtube_data}
    llm = _get_llm()
    topics_results = []

    for reddit in reddit_data:
        topic_name = reddit.get("topic_name", "")
        yt = yt_map.get(topic_name, {"topic_name": topic_name, "videos": []})

        topic_text = _build_topic_text(
            reddit,
            yt,
            max_comments=limits.max_comments_per_video,
            max_transcript_chars=limits.max_transcript_chars,
        )

        prompt = per_topic_validation_prompt(
            audience_name=state["audience_name"],
            topic_name=topic_name,
            topic_text=topic_text,
            language=state.get("language", "en"),
        )

        response = llm.invoke(prompt)
        content = extract_response_text(response)
        result = _parse_json_response(content)

        if result:
            topics_results.append(result)
        else:
            logger.warning("Per-topic analysis failed for '%s'", topic_name)

    if not topics_results:
        return {"analysis_result": None}

    # Aggregate per-topic results
    traction_scores = [t.get("traction_score", 0) for t in topics_results]
    avg_traction = sum(traction_scores) / len(traction_scores) if traction_scores else 0

    aggregated = {
        "topics": topics_results,
        "cross_platform_summary": {
            "total_topics_with_traction": sum(1 for s in traction_scores if s >= 5),
            "avg_traction_score": round(avg_traction, 1),
            "content_gaps_found": sum(
                1 for t in topics_results if t.get("content_gap")
            ),
            "key_findings": [],
            "best_opportunity": "",
            "biggest_divergence": "",
        },
    }

    logger.info(
        "Per-topic cross-platform analysis complete for %d topics",
        len(topics_results),
    )
    return {"analysis_result": aggregated}


# ── Node 2: Generate summary ──────────────────────────────────────────────


def generate_summary(state: YouTubeValidationState) -> dict:
    """Gera resumo executivo a partir do resultado completo."""
    result = state.get("analysis_result")
    if not result:
        return {"analysis_summary": None}

    llm = _get_llm()
    result_text = json.dumps(result, indent=2, ensure_ascii=False)

    # Truncate if too large for summary prompt
    if len(result_text) > 80_000:
        result_text = result_text[:80_000] + "\n... (truncated)"

    prompt = summary_prompt(
        audience_name=state["audience_name"],
        analysis_result_text=result_text,
        language=state.get("language", "en"),
    )

    response = llm.invoke(prompt)
    content = extract_response_text(response)
    summary = _parse_json_response(content)

    if not summary:
        # Fallback: build summary from analysis_result
        topics = result.get("topics", [])
        total_videos = sum(t.get("youtube_video_count", 0) for t in topics)
        traction_scores = [t.get("traction_score", 0) for t in topics]
        summary = {
            "topics_analyzed": len(topics),
            "topics_with_youtube_traction": sum(1 for s in traction_scores if s >= 5),
            "content_gaps_found": sum(1 for t in topics if t.get("content_gap")),
            "avg_traction_score": round(sum(traction_scores) / len(traction_scores), 1)
            if traction_scores
            else 0,
            "total_videos_analyzed": total_videos,
            "total_comments_analyzed": 0,
        }

    logger.info("Summary generated for cross-platform analysis")
    return {"analysis_summary": summary}


# ── Graph assembly ──────────────────────────────────────────────────────────


def create_youtube_validation_agent():
    """Create the LangGraph agent for YouTube cross-platform validation."""
    workflow = StateGraph(YouTubeValidationState)

    workflow.add_node("analyze_cross_platform", analyze_cross_platform)
    workflow.add_node("generate_summary", generate_summary)

    workflow.add_edge(START, "analyze_cross_platform")
    workflow.add_edge("analyze_cross_platform", "generate_summary")
    workflow.add_edge("generate_summary", END)

    return workflow.compile()
