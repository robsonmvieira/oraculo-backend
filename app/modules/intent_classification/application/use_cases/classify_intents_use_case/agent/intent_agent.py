"""Agente LangGraph para classificação de intenção de posts."""

import json
import logging
import os
import re
from collections import Counter

from langchain_openai import ChatOpenAI

from app.modules.shared.application.services.llm_factory import extract_response_text
from langgraph.graph import END, START, StateGraph

from app.modules.intent_classification.application.use_cases.classify_intents_use_case.agent.prompts.intent_prompts import (
    get_advice_patterns_prompt,
    get_aggregate_intents_prompt,
    get_analyze_advice_requests_prompt,
    get_analyze_ideas_prompt,
    get_analyze_pain_anger_prompt,
    get_analyze_solution_requests_prompt,
    get_classify_intents_prompt,
    get_ideas_patterns_prompt,
    get_pain_patterns_prompt,
    get_solution_patterns_prompt,
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

# Thread analysis configuration
TOP_POSTS_FOR_COMMENTS = 15
COMMENTS_PER_POST = 30
TOP_COMMENTS_IN_PROMPT = 5
MAX_COMMENT_LENGTH = 500
THREAD_ANALYSIS_ENABLED = True

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


def _fetch_comments_for_posts(
    posts: list[dict],
    reddit_provider,
    top_n: int = TOP_POSTS_FOR_COMMENTS,
    comments_per_post: int = COMMENTS_PER_POST,
    top_comments_in_prompt: int = TOP_COMMENTS_IN_PROMPT,
) -> dict[str, list[dict]]:
    """
    Busca comentários dos top N posts por num_comments.

    Returns:
        Dict mapping post_id -> list of top comments sorted by score.
    """
    sorted_posts = sorted(
        posts,
        key=lambda p: p.get("num_comments", 0),
        reverse=True,
    )[:top_n]

    comments_map: dict[str, list[dict]] = {}
    for post in sorted_posts:
        subreddit = post.get("subreddit", "")
        post_id = post.get("id", "")
        if not subreddit or not post_id:
            continue

        try:
            raw_comments = reddit_provider.get_post_comments(
                subreddit, post_id, limit=comments_per_post
            )
            sorted_comments = sorted(
                raw_comments, key=lambda c: c.score, reverse=True
            )[:top_comments_in_prompt]
            comments_map[post_id] = [
                {
                    "body": c.body,
                    "score": c.score,
                    "author": c.author or "anonymous",
                }
                for c in sorted_comments
            ]
        except Exception:
            logger.warning("Failed to fetch comments for post %s", post_id)
            comments_map[post_id] = []

    return comments_map


def _build_posts_with_comments_text(
    posts: list[dict],
    comments_map: dict[str, list[dict]],
    max_chars: int = MAX_POSTS_CHARS,
) -> str:
    """Formata batch de posts COM comentários para o prompt de patterns."""
    lines: list[str] = []
    total_chars = 0

    for post in posts:
        selftext = (post.get("selftext") or "")[:500]
        entry = (
            f"[POST_ID: {post['id']}] "
            f"r/{post['subreddit']} | score: {post.get('score', 0)} | "
            f"comments: {post.get('num_comments', 0)}\n"
            f"Title: {post['title']}\n"
        )
        if selftext.strip():
            entry += f"Body: {selftext}\n"

        post_comments = comments_map.get(post["id"], [])
        if post_comments:
            entry += "--- Top Comments ---\n"
            for comment in post_comments:
                body = comment["body"].strip()
                if len(body) > MAX_COMMENT_LENGTH:
                    body = body[:MAX_COMMENT_LENGTH] + "..."
                entry += (
                    f"  [{comment['author']}, score:{comment['score']}] {body}\n"
                )

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


def _validate_and_build_classified_post(
    result: dict, post_lookup: dict[str, dict]
) -> ClassifiedPost | None:
    """Valida um resultado de classificação e constrói o ClassifiedPost."""
    post_id = result.get("post_id", "")
    primary = result.get("primary_intent", "")
    secondary = result.get("secondary_intent")

    if primary not in VALID_INTENTS:
        logger.warning("Invalid primary_intent '%s' for post %s, skipping", primary, post_id)
        return None

    if secondary and secondary not in VALID_INTENTS:
        secondary = None

    original = post_lookup.get(post_id)
    if not original:
        logger.warning("Post ID '%s' not found in batch, skipping", post_id)
        return None

    raw_confidence = result.get("confidence", "medium")
    confidence = raw_confidence if raw_confidence in ("high", "medium", "low") else "medium"

    return ClassifiedPost(
        post_id=post_id,
        post_title=original["title"],
        post_subreddit=original["subreddit"],
        primary_intent=primary,
        secondary_intent=secondary,
        confidence=confidence,
    )


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
        batch_results = _parse_json_response(extract_response_text(response))

        for result in batch_results:
            classified = _validate_and_build_classified_post(result, post_lookup)
            if classified:
                all_classified.append(classified)

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

        # Sample posts (primeiros 5)
        sample = [
            {"title": p["post_title"], "subreddit": p["post_subreddit"]}
            for p in posts_in_cat[:5]
        ]

        aggregations.append(
            {
                "category": category,
                "post_count": len(posts_in_cat),
                "sample_posts": sample,
                "subcategories": None,
                "topic_keywords": None,
                "top_subreddits": None,
                "pain_patterns": None,
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
        descriptions = _parse_json_response(extract_response_text(response))

        # Mapear descrições para agregações
        desc_map = {
            d["category"]: d["description"] for d in descriptions if "category" in d
        }
        for agg in aggregations:
            agg["description"] = desc_map.get(agg["category"])

    logger.info("Aggregated %d intent categories", len(aggregations))
    return {"intent_aggregations": aggregations}


def _parse_json_object_response(content: str) -> dict:
    """Extrai objeto JSON da resposta do LLM."""
    cleaned = content.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    try:
        result = json.loads(cleaned)
        if isinstance(result, dict):
            return result
        return {}
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM JSON object response")
        return {}


def analyze_pain_anger(state: IntentClassificationState) -> dict:
    """
    Nó 3: Analisa posts pain_and_anger para extrair subcategorias de sentimento e tópicos.

    Envia TODOS os posts classificados como pain_and_anger ao LLM em uma única chamada
    para obter distribuições agregadas de sentimentos e topic keywords.
    Também computa top_subreddits (de quais comunidades vêm os posts pain_and_anger).
    Opcionalmente, agrupa posts em padrões de dor comportamentais (segunda chamada LLM).
    Enriquece com comentários dos top posts quando reddit_provider disponível.
    """
    aggregations = state.get("intent_aggregations", [])
    classified = state.get("classified_posts", [])

    # Filtrar posts pain_and_anger
    pain_posts = [p for p in classified if p["primary_intent"] == "pain_and_anger"]
    if not pain_posts:
        return {"intent_aggregations": aggregations}

    # Computar top_subreddits a partir dos posts pain_and_anger
    subreddit_counter = Counter(p["post_subreddit"] for p in pain_posts)
    top_subreddits = [
        {"name": name, "count": count}
        for name, count in subreddit_counter.most_common(10)
    ]

    # Construir texto de posts para o prompt
    posts_text = _build_posts_batch_text(
        [
            {
                "id": p["post_id"],
                "subreddit": p["post_subreddit"],
                "title": p["post_title"],
                "score": 0,
                "num_comments": 0,
            }
            for p in pain_posts
        ]
    )

    llm = _get_llm()
    language_directive = get_language_directive(state.get("language", "en"))

    prompt = get_analyze_pain_anger_prompt(
        audience_name=state["audience_name"],
        period_start=state["period_start"],
        period_end=state["period_end"],
        posts_text=posts_text,
        total_posts=len(pain_posts),
        language_directive=language_directive,
    )

    response = llm.invoke(prompt)
    result = _parse_json_object_response(extract_response_text(response))

    subcategories = result.get("subcategories")
    topic_keywords = result.get("topic_keywords")

    # Validar e limitar a 10 itens
    if isinstance(subcategories, dict):
        subcategories = dict(
            sorted(subcategories.items(), key=lambda x: x[1], reverse=True)[:10]
        )
    else:
        subcategories = None

    if isinstance(topic_keywords, dict):
        topic_keywords = dict(
            sorted(topic_keywords.items(), key=lambda x: x[1], reverse=True)[:10]
        )
    else:
        topic_keywords = None

    # --- Pain Patterns (segunda chamada LLM) ---
    pain_patterns = []
    if len(pain_posts) >= 3:
        # Lookup de posts completos (com selftext, score, num_comments, permalink)
        full_posts_map = {p["id"]: p for p in state.get("posts", [])}

        # Montar texto rico para o prompt (inclui selftext)
        rich_posts = [
            full_posts_map[p["post_id"]]
            for p in pain_posts
            if p["post_id"] in full_posts_map
        ]

        # Buscar comentários se reddit_provider disponível
        reddit_provider = state.get("reddit_provider")
        comments_map: dict[str, list[dict]] = {}
        has_comments = False
        if reddit_provider and THREAD_ANALYSIS_ENABLED:
            logger.info(
                "Fetching comments for top %d pain_and_anger posts",
                TOP_POSTS_FOR_COMMENTS,
            )
            comments_map = _fetch_comments_for_posts(rich_posts, reddit_provider)
            has_comments = bool(comments_map)
            logger.info("Fetched comments for %d pain_and_anger posts", len(comments_map))

        # Usar texto com ou sem comentários
        if has_comments:
            patterns_text = _build_posts_with_comments_text(rich_posts, comments_map)
        else:
            patterns_text = _build_posts_batch_text(rich_posts)

        patterns_prompt = get_pain_patterns_prompt(
            audience_name=state["audience_name"],
            period_start=state["period_start"],
            period_end=state["period_end"],
            posts_text=patterns_text,
            total_posts=len(pain_posts),
            language_directive=language_directive,
            has_comments=has_comments,
        )

        try:
            patterns_response = llm.invoke(patterns_prompt)
            raw_patterns = _parse_json_response(
                extract_response_text(patterns_response)
            )

            # Enriquecer cada padrão com métricas e submissions
            for pattern in raw_patterns:
                submissions = []
                total_upvotes = 0
                total_comments = 0
                for pid in pattern.get("post_ids", []):
                    fp = full_posts_map.get(pid)
                    if not fp:
                        continue
                    submission = {
                        "title": fp["title"],
                        "body": (fp.get("selftext") or "")[:500],
                        "subreddit": f"r/{fp['subreddit']}",
                        "score": fp.get("score", 0),
                        "num_comments": fp.get("num_comments", 0),
                        "permalink": fp.get("permalink", ""),
                    }
                    if has_comments and pid in comments_map:
                        submission["top_comments"] = comments_map[pid]
                    submissions.append(submission)
                    total_upvotes += fp.get("score", 0)
                    total_comments += fp.get("num_comments", 0)

                if submissions:
                    pattern_entry = {
                        "name": pattern.get("name", ""),
                        "emoji": pattern.get("emoji", ""),
                        "post_count": len(submissions),
                        "total_upvotes": total_upvotes,
                        "total_comments": total_comments,
                        "submissions": submissions,
                    }
                    if has_comments:
                        pattern_entry["validation_score"] = pattern.get(
                            "validation_score", "low"
                        )
                        pattern_entry["suggested_coping"] = pattern.get(
                            "suggested_coping", []
                        )
                    pain_patterns.append(pattern_entry)

            pain_patterns.sort(key=lambda x: x["post_count"], reverse=True)
            logger.info(
                "Pain patterns: %d patterns identified from %d posts (comments: %s)",
                len(pain_patterns),
                len(pain_posts),
                "yes" if has_comments else "no",
            )
        except Exception:
            logger.exception("Failed to extract pain patterns, continuing without them")
            pain_patterns = []

    # Atualizar a agregação de pain_and_anger
    updated = []
    for agg in aggregations:
        if agg["category"] == "pain_and_anger":
            agg = {
                **agg,
                "subcategories": subcategories,
                "topic_keywords": topic_keywords,
                "top_subreddits": top_subreddits,
                "pain_patterns": pain_patterns,
            }
        updated.append(agg)

    logger.info(
        "Pain & Anger analysis: %d subcategories, %d topic keywords, %d subreddits",
        len(subcategories) if subcategories else 0,
        len(topic_keywords) if topic_keywords else 0,
        len(top_subreddits),
    )
    return {"intent_aggregations": updated}


def analyze_solution_requests(state: IntentClassificationState) -> dict:
    """
    Nó 4: Analisa posts solution_request para extrair tipos de solução e tópicos.

    Envia TODOS os posts classificados como solution_request ao LLM em uma única chamada
    para obter distribuições agregadas de tipos de solução e topic keywords.
    Também computa top_subreddits (de quais comunidades vêm os posts solution_request).
    Opcionalmente, agrupa posts em padrões de busca de solução (segunda chamada LLM).
    Enriquece com comentários dos top posts quando reddit_provider disponível.
    """
    aggregations = state.get("intent_aggregations", [])
    classified = state.get("classified_posts", [])

    # Filtrar posts solution_request
    solution_posts = [p for p in classified if p["primary_intent"] == "solution_request"]
    if not solution_posts:
        return {"intent_aggregations": aggregations}

    # Computar top_subreddits a partir dos posts solution_request
    subreddit_counter = Counter(p["post_subreddit"] for p in solution_posts)
    top_subreddits = [
        {"name": name, "count": count}
        for name, count in subreddit_counter.most_common(10)
    ]

    # Construir texto de posts para o prompt
    posts_text = _build_posts_batch_text(
        [
            {
                "id": p["post_id"],
                "subreddit": p["post_subreddit"],
                "title": p["post_title"],
                "score": 0,
                "num_comments": 0,
            }
            for p in solution_posts
        ]
    )

    llm = _get_llm()
    language_directive = get_language_directive(state.get("language", "en"))

    prompt = get_analyze_solution_requests_prompt(
        audience_name=state["audience_name"],
        period_start=state["period_start"],
        period_end=state["period_end"],
        posts_text=posts_text,
        total_posts=len(solution_posts),
        language_directive=language_directive,
    )

    response = llm.invoke(prompt)
    result = _parse_json_object_response(extract_response_text(response))

    subcategories = result.get("subcategories")
    topic_keywords = result.get("topic_keywords")

    # Validar e limitar a 10 itens
    if isinstance(subcategories, dict):
        subcategories = dict(
            sorted(subcategories.items(), key=lambda x: x[1], reverse=True)[:10]
        )
    else:
        subcategories = None

    if isinstance(topic_keywords, dict):
        topic_keywords = dict(
            sorted(topic_keywords.items(), key=lambda x: x[1], reverse=True)[:10]
        )
    else:
        topic_keywords = None

    # --- Solution Patterns (segunda chamada LLM) ---
    solution_patterns = []
    if len(solution_posts) >= 3:
        # Lookup de posts completos (com selftext, score, num_comments, permalink)
        full_posts_map = {p["id"]: p for p in state.get("posts", [])}

        # Montar texto rico para o prompt (inclui selftext)
        rich_posts = [
            full_posts_map[p["post_id"]]
            for p in solution_posts
            if p["post_id"] in full_posts_map
        ]

        # Buscar comentários se reddit_provider disponível
        reddit_provider = state.get("reddit_provider")
        comments_map: dict[str, list[dict]] = {}
        has_comments = False
        if reddit_provider and THREAD_ANALYSIS_ENABLED:
            logger.info(
                "Fetching comments for top %d solution_request posts",
                TOP_POSTS_FOR_COMMENTS,
            )
            comments_map = _fetch_comments_for_posts(rich_posts, reddit_provider)
            has_comments = bool(comments_map)
            logger.info("Fetched comments for %d solution_request posts", len(comments_map))

        # Usar texto com ou sem comentários
        if has_comments:
            patterns_text = _build_posts_with_comments_text(rich_posts, comments_map)
        else:
            patterns_text = _build_posts_batch_text(rich_posts)

        patterns_prompt = get_solution_patterns_prompt(
            audience_name=state["audience_name"],
            period_start=state["period_start"],
            period_end=state["period_end"],
            posts_text=patterns_text,
            total_posts=len(solution_posts),
            language_directive=language_directive,
            has_comments=has_comments,
        )

        try:
            patterns_response = llm.invoke(patterns_prompt)
            raw_patterns = _parse_json_response(
                extract_response_text(patterns_response)
            )

            # Enriquecer cada padrão com métricas e submissions
            for pattern in raw_patterns:
                submissions = []
                total_upvotes = 0
                total_comments = 0
                for pid in pattern.get("post_ids", []):
                    fp = full_posts_map.get(pid)
                    if not fp:
                        continue
                    submission = {
                        "title": fp["title"],
                        "body": (fp.get("selftext") or "")[:500],
                        "subreddit": f"r/{fp['subreddit']}",
                        "score": fp.get("score", 0),
                        "num_comments": fp.get("num_comments", 0),
                        "permalink": fp.get("permalink", ""),
                    }
                    if has_comments and pid in comments_map:
                        submission["top_comments"] = comments_map[pid]
                    submissions.append(submission)
                    total_upvotes += fp.get("score", 0)
                    total_comments += fp.get("num_comments", 0)

                if submissions:
                    pattern_entry = {
                        "name": pattern.get("name", ""),
                        "emoji": pattern.get("emoji", ""),
                        "post_count": len(submissions),
                        "total_upvotes": total_upvotes,
                        "total_comments": total_comments,
                        "submissions": submissions,
                    }
                    if has_comments:
                        pattern_entry["recommended_solutions"] = pattern.get(
                            "recommended_solutions", []
                        )
                        pattern_entry["community_consensus"] = pattern.get(
                            "community_consensus", "weak"
                        )
                    solution_patterns.append(pattern_entry)

            solution_patterns.sort(key=lambda x: x["post_count"], reverse=True)
            logger.info(
                "Solution patterns: %d patterns identified from %d posts (comments: %s)",
                len(solution_patterns),
                len(solution_posts),
                "yes" if has_comments else "no",
            )
        except Exception:
            logger.exception("Failed to extract solution patterns, continuing without them")
            solution_patterns = []

    # Atualizar a agregação de solution_request
    updated = []
    for agg in aggregations:
        if agg["category"] == "solution_request":
            agg = {
                **agg,
                "subcategories": subcategories,
                "topic_keywords": topic_keywords,
                "top_subreddits": top_subreddits,
                "pain_patterns": solution_patterns,
            }
        updated.append(agg)

    logger.info(
        "Solution Requests analysis: %d subcategories, %d topic keywords, %d subreddits",
        len(subcategories) if subcategories else 0,
        len(topic_keywords) if topic_keywords else 0,
        len(top_subreddits),
    )
    return {"intent_aggregations": updated}


def analyze_advice_requests(state: IntentClassificationState) -> dict:
    """
    Nó 5: Analisa posts advice_request para extrair tipos de conselho e tópicos.

    Envia TODOS os posts classificados como advice_request ao LLM em uma única chamada
    para obter distribuições agregadas de tipos de conselho e topic keywords.
    Também computa top_subreddits (de quais comunidades vêm os posts advice_request).
    Opcionalmente, agrupa posts em padrões de busca de conselho (segunda chamada LLM).
    """
    aggregations = state.get("intent_aggregations", [])
    classified = state.get("classified_posts", [])

    # Filtrar posts advice_request
    advice_posts = [p for p in classified if p["primary_intent"] == "advice_request"]
    if not advice_posts:
        return {"intent_aggregations": aggregations}

    # Computar top_subreddits a partir dos posts advice_request
    subreddit_counter = Counter(p["post_subreddit"] for p in advice_posts)
    top_subreddits = [
        {"name": name, "count": count}
        for name, count in subreddit_counter.most_common(10)
    ]

    # Construir texto de posts para o prompt
    posts_text = _build_posts_batch_text(
        [
            {
                "id": p["post_id"],
                "subreddit": p["post_subreddit"],
                "title": p["post_title"],
                "score": 0,
                "num_comments": 0,
            }
            for p in advice_posts
        ]
    )

    llm = _get_llm()
    language_directive = get_language_directive(state.get("language", "en"))

    prompt = get_analyze_advice_requests_prompt(
        audience_name=state["audience_name"],
        period_start=state["period_start"],
        period_end=state["period_end"],
        posts_text=posts_text,
        total_posts=len(advice_posts),
        language_directive=language_directive,
    )

    response = llm.invoke(prompt)
    result = _parse_json_object_response(extract_response_text(response))

    subcategories = result.get("subcategories")
    topic_keywords = result.get("topic_keywords")

    # Validar e limitar a 10 itens
    if isinstance(subcategories, dict):
        subcategories = dict(
            sorted(subcategories.items(), key=lambda x: x[1], reverse=True)[:10]
        )
    else:
        subcategories = None

    if isinstance(topic_keywords, dict):
        topic_keywords = dict(
            sorted(topic_keywords.items(), key=lambda x: x[1], reverse=True)[:10]
        )
    else:
        topic_keywords = None

    # --- Advice Patterns (segunda chamada LLM) ---
    advice_patterns = []
    if len(advice_posts) >= 3:
        # Lookup de posts completos (com selftext, score, num_comments, permalink)
        full_posts_map = {p["id"]: p for p in state.get("posts", [])}

        # Montar texto rico para o prompt (inclui selftext)
        rich_posts = [
            full_posts_map[p["post_id"]]
            for p in advice_posts
            if p["post_id"] in full_posts_map
        ]
        patterns_text = _build_posts_batch_text(rich_posts)

        patterns_prompt = get_advice_patterns_prompt(
            audience_name=state["audience_name"],
            period_start=state["period_start"],
            period_end=state["period_end"],
            posts_text=patterns_text,
            total_posts=len(advice_posts),
            language_directive=language_directive,
        )

        try:
            patterns_response = llm.invoke(patterns_prompt)
            raw_patterns = _parse_json_response(
                extract_response_text(patterns_response)
            )

            # Enriquecer cada padrão com métricas e submissions
            for pattern in raw_patterns:
                submissions = []
                total_upvotes = 0
                total_comments = 0
                for pid in pattern.get("post_ids", []):
                    fp = full_posts_map.get(pid)
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
                        }
                    )
                    total_upvotes += fp.get("score", 0)
                    total_comments += fp.get("num_comments", 0)

                if submissions:
                    advice_patterns.append(
                        {
                            "name": pattern.get("name", ""),
                            "emoji": pattern.get("emoji", ""),
                            "post_count": len(submissions),
                            "total_upvotes": total_upvotes,
                            "total_comments": total_comments,
                            "submissions": submissions,
                        }
                    )

            advice_patterns.sort(key=lambda x: x["post_count"], reverse=True)
            logger.info(
                "Advice patterns: %d patterns identified from %d posts",
                len(advice_patterns),
                len(advice_posts),
            )
        except Exception:
            logger.exception("Failed to extract advice patterns, continuing without them")
            advice_patterns = []

    # Atualizar a agregação de advice_request
    updated = []
    for agg in aggregations:
        if agg["category"] == "advice_request":
            agg = {
                **agg,
                "subcategories": subcategories,
                "topic_keywords": topic_keywords,
                "top_subreddits": top_subreddits,
                "pain_patterns": advice_patterns,
            }
        updated.append(agg)

    logger.info(
        "Advice Requests analysis: %d subcategories, %d topic keywords, %d subreddits",
        len(subcategories) if subcategories else 0,
        len(topic_keywords) if topic_keywords else 0,
        len(top_subreddits),
    )
    return {"intent_aggregations": updated}


def analyze_ideas(state: IntentClassificationState) -> dict:
    """
    Nó 6: Analisa posts ideas para extrair tipos de ideia e tópicos.

    Envia TODOS os posts classificados como ideas ao LLM em uma única chamada
    para obter distribuições agregadas de tipos de ideia e topic keywords.
    Também computa top_subreddits (de quais comunidades vêm os posts ideas).
    Opcionalmente, agrupa posts em padrões de inovação (segunda chamada LLM).
    Enriquece com comentários dos top posts quando reddit_provider disponível.
    """
    aggregations = state.get("intent_aggregations", [])
    classified = state.get("classified_posts", [])

    # Filtrar posts ideas
    ideas_posts = [p for p in classified if p["primary_intent"] == "ideas"]
    if not ideas_posts:
        return {"intent_aggregations": aggregations}

    # Computar top_subreddits a partir dos posts ideas
    subreddit_counter = Counter(p["post_subreddit"] for p in ideas_posts)
    top_subreddits = [
        {"name": name, "count": count}
        for name, count in subreddit_counter.most_common(10)
    ]

    # Construir texto de posts para o prompt
    posts_text = _build_posts_batch_text(
        [
            {
                "id": p["post_id"],
                "subreddit": p["post_subreddit"],
                "title": p["post_title"],
                "score": 0,
                "num_comments": 0,
            }
            for p in ideas_posts
        ]
    )

    llm = _get_llm()
    language_directive = get_language_directive(state.get("language", "en"))

    prompt = get_analyze_ideas_prompt(
        audience_name=state["audience_name"],
        period_start=state["period_start"],
        period_end=state["period_end"],
        posts_text=posts_text,
        total_posts=len(ideas_posts),
        language_directive=language_directive,
    )

    response = llm.invoke(prompt)
    result = _parse_json_object_response(extract_response_text(response))

    subcategories = result.get("subcategories")
    topic_keywords = result.get("topic_keywords")

    # Validar e limitar a 10 itens
    if isinstance(subcategories, dict):
        subcategories = dict(
            sorted(subcategories.items(), key=lambda x: x[1], reverse=True)[:10]
        )
    else:
        subcategories = None

    if isinstance(topic_keywords, dict):
        topic_keywords = dict(
            sorted(topic_keywords.items(), key=lambda x: x[1], reverse=True)[:10]
        )
    else:
        topic_keywords = None

    # --- Ideas Patterns (segunda chamada LLM) ---
    ideas_patterns = []
    if len(ideas_posts) >= 3:
        # Lookup de posts completos (com selftext, score, num_comments, permalink)
        full_posts_map = {p["id"]: p for p in state.get("posts", [])}

        # Montar texto rico para o prompt (inclui selftext)
        rich_posts = [
            full_posts_map[p["post_id"]]
            for p in ideas_posts
            if p["post_id"] in full_posts_map
        ]

        # Buscar comentários se reddit_provider disponível
        reddit_provider = state.get("reddit_provider")
        comments_map: dict[str, list[dict]] = {}
        has_comments = False
        if reddit_provider and THREAD_ANALYSIS_ENABLED:
            logger.info(
                "Fetching comments for top %d ideas posts",
                TOP_POSTS_FOR_COMMENTS,
            )
            comments_map = _fetch_comments_for_posts(rich_posts, reddit_provider)
            has_comments = bool(comments_map)
            logger.info("Fetched comments for %d ideas posts", len(comments_map))

        # Usar texto com ou sem comentários
        if has_comments:
            patterns_text = _build_posts_with_comments_text(rich_posts, comments_map)
        else:
            patterns_text = _build_posts_batch_text(rich_posts)

        patterns_prompt = get_ideas_patterns_prompt(
            audience_name=state["audience_name"],
            period_start=state["period_start"],
            period_end=state["period_end"],
            posts_text=patterns_text,
            total_posts=len(ideas_posts),
            language_directive=language_directive,
            has_comments=has_comments,
        )

        try:
            patterns_response = llm.invoke(patterns_prompt)
            raw_patterns = _parse_json_response(
                extract_response_text(patterns_response)
            )

            # Enriquecer cada padrão com métricas e submissions
            for pattern in raw_patterns:
                submissions = []
                total_upvotes = 0
                total_comments = 0
                for pid in pattern.get("post_ids", []):
                    fp = full_posts_map.get(pid)
                    if not fp:
                        continue
                    submission = {
                        "title": fp["title"],
                        "body": (fp.get("selftext") or "")[:500],
                        "subreddit": f"r/{fp['subreddit']}",
                        "score": fp.get("score", 0),
                        "num_comments": fp.get("num_comments", 0),
                        "permalink": fp.get("permalink", ""),
                    }
                    if has_comments and pid in comments_map:
                        submission["top_comments"] = comments_map[pid]
                    submissions.append(submission)
                    total_upvotes += fp.get("score", 0)
                    total_comments += fp.get("num_comments", 0)

                if submissions:
                    pattern_entry = {
                        "name": pattern.get("name", ""),
                        "emoji": pattern.get("emoji", ""),
                        "post_count": len(submissions),
                        "total_upvotes": total_upvotes,
                        "total_comments": total_comments,
                        "submissions": submissions,
                    }
                    if has_comments:
                        pattern_entry["community_reception"] = pattern.get(
                            "community_reception", "mixed"
                        )
                        pattern_entry["refinements"] = pattern.get(
                            "refinements", []
                        )
                        pattern_entry["feasibility_notes"] = pattern.get(
                            "feasibility_notes", []
                        )
                    ideas_patterns.append(pattern_entry)

            ideas_patterns.sort(key=lambda x: x["post_count"], reverse=True)
            logger.info(
                "Ideas patterns: %d patterns identified from %d posts (comments: %s)",
                len(ideas_patterns),
                len(ideas_posts),
                "yes" if has_comments else "no",
            )
        except Exception:
            logger.exception("Failed to extract ideas patterns, continuing without them")
            ideas_patterns = []

    # Atualizar a agregação de ideas
    updated = []
    for agg in aggregations:
        if agg["category"] == "ideas":
            agg = {
                **agg,
                "subcategories": subcategories,
                "topic_keywords": topic_keywords,
                "top_subreddits": top_subreddits,
                "pain_patterns": ideas_patterns,
            }
        updated.append(agg)

    logger.info(
        "Ideas analysis: %d subcategories, %d topic keywords, %d subreddits",
        len(subcategories) if subcategories else 0,
        len(topic_keywords) if topic_keywords else 0,
        len(top_subreddits),
    )
    return {"intent_aggregations": updated}


def create_intent_classification_agent():
    """Cria e compila o grafo LangGraph de classificação de intenção."""
    workflow = StateGraph(IntentClassificationState)
    workflow.add_node("classify_intents", classify_intents)
    workflow.add_node("aggregate_intents", aggregate_intents)
    workflow.add_node("analyze_pain_anger", analyze_pain_anger)
    workflow.add_node("analyze_solution_requests", analyze_solution_requests)
    workflow.add_node("analyze_advice_requests", analyze_advice_requests)
    workflow.add_node("analyze_ideas", analyze_ideas)
    workflow.add_edge(START, "classify_intents")
    workflow.add_edge("classify_intents", "aggregate_intents")
    workflow.add_edge("aggregate_intents", "analyze_pain_anger")
    workflow.add_edge("analyze_pain_anger", "analyze_solution_requests")
    workflow.add_edge("analyze_solution_requests", "analyze_advice_requests")
    workflow.add_edge("analyze_advice_requests", "analyze_ideas")
    workflow.add_edge("analyze_ideas", END)
    return workflow.compile()
