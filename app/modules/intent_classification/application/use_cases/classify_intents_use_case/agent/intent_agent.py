"""Agente LangGraph para classificação de intenção de posts."""

import json
import logging
import os
import re
from collections import Counter

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.modules.intent_classification.application.use_cases.classify_intents_use_case.agent.prompts.intent_prompts import (
    get_aggregate_intents_prompt,
    get_classify_intents_prompt,
)
from app.modules.intent_classification.application.use_cases.classify_intents_use_case.agent.state import (
    ClassifiedPost,
    IntentClassificationState,
)
from app.modules.shared.application.helpers.language_directive import (
    get_language_directive,
)

logger = logging.getLogger(__name__)

MAX_POSTS_CHARS = 80_000
BATCH_SIZE = 50

VALID_INTENTS = {
    "advice_request",
    "pain_and_anger",
    "solution_request",
    "self_promotion",
    "ideas",
    "news",
}

INTENT_CATEGORIES = {
    "advice_request": {"label": "Advice Requests", "icon": "help-circle"},
    "pain_and_anger": {"label": "Pain & Anger", "icon": "flame"},
    "solution_request": {"label": "Solution Requests", "icon": "search"},
    "self_promotion": {"label": "Self-Promotion", "icon": "megaphone"},
    "ideas": {"label": "Ideas", "icon": "lightbulb"},
    "news": {"label": "News", "icon": "newspaper"},
}


def _get_llm() -> ChatOpenAI:
    """Retorna instância do LLM configurada."""
    model_name = os.getenv("MODEL_NAME", "gpt-5-nano-2025-08-07")
    return ChatOpenAI(model=model_name, temperature=0)


def _build_posts_batch_text(posts: list[dict], max_chars: int = MAX_POSTS_CHARS) -> str:
    """Formata batch de posts para injeção no prompt."""
    lines: list[str] = []
    total_chars = 0

    for post in posts:
        selftext = (post.get("selftext") or "")[:300]
        entry = (
            f"[POST_ID: {post['id']}] "
            f"r/{post['subreddit']} | score: {post.get('score', 0)} | "
            f"comments: {post.get('num_comments', 0)}\n"
            f"Title: {post['title']}\n"
        )
        if selftext.strip():
            entry += f"Body: {selftext}\n"
        entry += "---\n"

        if total_chars + len(entry) > max_chars:
            break
        lines.append(entry)
        total_chars += len(entry)

    return "".join(lines)


def _parse_json_response(content: str) -> list[dict]:
    """Extrai array JSON da resposta do LLM."""
    cleaned = content.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    try:
        result = json.loads(cleaned)
        if isinstance(result, list):
            return result
        return []
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM JSON response")
        return []


def classify_intents(state: IntentClassificationState) -> dict:
    """
    Nó 1: Classifica cada post por intenção em batches.

    Processa posts em grupos de BATCH_SIZE, chamando o LLM para cada batch.
    Valida categorias retornadas contra as 6 categorias válidas.
    """
    posts = state.get("posts", [])
    if not posts:
        return {"classified_posts": []}

    llm = _get_llm()
    language_directive = get_language_directive(state.get("language", "en"))
    communities_str = ", ".join(state.get("community_names", []))

    # Lookup para mapear post_id → dados completos
    post_lookup = {p["id"]: p for p in posts}
    all_classified: list[ClassifiedPost] = []

    # Processar em batches
    for i in range(0, len(posts), BATCH_SIZE):
        batch = posts[i : i + BATCH_SIZE]
        batch_text = _build_posts_batch_text(batch)

        prompt = get_classify_intents_prompt(
            audience_name=state["audience_name"],
            communities_str=communities_str,
            period_start=state["period_start"],
            period_end=state["period_end"],
            posts_batch_text=batch_text,
            language_directive=language_directive,
        )

        response = llm.invoke(prompt)
        batch_results = _parse_json_response(response.content)

        for result in batch_results:
            post_id = result.get("post_id", "")
            primary = result.get("primary_intent", "")
            secondary = result.get("secondary_intent")

            # Validar categoria
            if primary not in VALID_INTENTS:
                logger.warning(
                    "Invalid primary_intent '%s' for post %s, skipping",
                    primary,
                    post_id,
                )
                continue

            if secondary and secondary not in VALID_INTENTS:
                secondary = None

            # Buscar dados do post original
            original = post_lookup.get(post_id)
            if not original:
                logger.warning("Post ID '%s' not found in batch, skipping", post_id)
                continue

            all_classified.append(
                ClassifiedPost(
                    post_id=post_id,
                    post_title=original["title"],
                    post_subreddit=original["subreddit"],
                    primary_intent=primary,
                    secondary_intent=secondary,
                    confidence=result.get("confidence", "medium"),
                )
            )

        logger.info(
            "Classified batch %d-%d: %d posts",
            i + 1,
            min(i + BATCH_SIZE, len(posts)),
            len(batch_results),
        )

    logger.info("Total classified: %d / %d posts", len(all_classified), len(posts))
    return {"classified_posts": all_classified}


def aggregate_intents(state: IntentClassificationState) -> dict:
    """
    Nó 2: Agrega classificações por categoria e gera descrições.

    Agrupa posts classificados, calcula métricas por categoria,
    e chama o LLM para gerar descrições de negócio.
    """
    classified = state.get("classified_posts", [])
    if not classified:
        return {"intent_aggregations": []}

    # 1. Agrupar por primary_intent
    groups: dict[str, list[ClassifiedPost]] = {}
    for post in classified:
        cat = post["primary_intent"]
        if cat not in groups:
            groups[cat] = []
        groups[cat].append(post)

    # 2. Construir métricas por categoria
    aggregations = []
    for category in INTENT_CATEGORIES:
        posts_in_cat = groups.get(category, [])
        if not posts_in_cat:
            continue

        # Top subreddits por frequência
        sub_counter = Counter(p["post_subreddit"] for p in posts_in_cat)
        top_subs = [
            {"name": name, "count": count} for name, count in sub_counter.most_common(5)
        ]

        # Sample posts (primeiros 5 — já que não temos score individual no ClassifiedPost,
        # usamos os primeiros 5 como representativos)
        sample = [
            {"title": p["post_title"], "subreddit": p["post_subreddit"]}
            for p in posts_in_cat[:5]
        ]

        aggregations.append(
            {
                "category": category,
                "post_count": len(posts_in_cat),
                "top_subreddits": top_subs,
                "sample_posts": sample,
            }
        )

    # 3. Ordenar por post_count desc e atribuir rank
    aggregations.sort(key=lambda x: x["post_count"], reverse=True)
    for rank, agg in enumerate(aggregations, 1):
        agg["rank"] = rank

    # 4. Chamar LLM para gerar descrições
    if aggregations:
        llm = _get_llm()
        language_directive = get_language_directive(state.get("language", "en"))

        intent_counts = [
            {
                "category": a["category"],
                "post_count": a["post_count"],
                "top_subreddits": [s["name"] for s in a["top_subreddits"][:3]],
                "sample_titles": [s["title"] for s in a["sample_posts"][:3]],
            }
            for a in aggregations
        ]

        prompt = get_aggregate_intents_prompt(
            audience_name=state["audience_name"],
            period_start=state["period_start"],
            period_end=state["period_end"],
            intent_counts_json=json.dumps(intent_counts, indent=2),
            language_directive=language_directive,
        )

        response = llm.invoke(prompt)
        descriptions = _parse_json_response(response.content)

        # Mapear descrições para agregações
        desc_map = {
            d["category"]: d["description"] for d in descriptions if "category" in d
        }
        for agg in aggregations:
            agg["description"] = desc_map.get(agg["category"])

    logger.info("Aggregated %d intent categories", len(aggregations))
    return {"intent_aggregations": aggregations}


def create_intent_classification_agent():
    """Cria e compila o grafo LangGraph de classificação de intenção."""
    workflow = StateGraph(IntentClassificationState)
    workflow.add_node("classify_intents", classify_intents)
    workflow.add_node("aggregate_intents", aggregate_intents)
    workflow.add_edge(START, "classify_intents")
    workflow.add_edge("classify_intents", "aggregate_intents")
    workflow.add_edge("aggregate_intents", END)
    return workflow.compile()
