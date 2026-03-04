"""Agente LangGraph para extração e análise de Product Intelligence."""

import json
import logging
import os
from collections import defaultdict

from langgraph.graph import END, START, StateGraph

from app.modules.product_intelligence.application.use_cases.extract_product_intelligence_use_case.agent.prompts.product_intelligence_prompts import (
    detect_opportunities_prompt,
    extract_products_prompt,
)
from app.modules.product_intelligence.application.use_cases.extract_product_intelligence_use_case.agent.state import (
    ProductIntelligenceState,
)
from app.modules.shared.application.services.llm_factory import (
    ContextLimits,
    create_llm,
    extract_response_text,
    get_context_limits,
)

logger = logging.getLogger(__name__)

_MODEL_ENV = "PRODUCT_INTELLIGENCE_MODEL_NAME"
_MODEL_FALLBACK_ENV = "MODEL_NAME"
_DEFAULT_MODEL = "gpt-5-nano-2025-08-07"

_OPENAI_OVERRIDES = {
    "max_posts_chars": 120_000,
    "max_comment_length": 500,
    "comments_per_post": 0,
    "max_selftext_length": 800,
    "top_posts_for_comments": 0,
    "comments_per_post_fetch": 0,
}


def _resolve_model_env() -> str:
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


def _build_posts_text(posts: list[dict], limits: ContextLimits) -> str:
    """Formata posts como texto para o prompt, respeitando limites de contexto."""
    lines: list[str] = []
    total_chars = 0
    max_selftext = limits.max_selftext_length

    for i, post in enumerate(posts, 1):
        title = post.get("title", "")
        selftext = post.get("selftext", "") or ""
        if len(selftext) > max_selftext:
            selftext = selftext[:max_selftext] + "..."

        subreddit = post.get("subreddit", "unknown")
        score = post.get("score", 0)

        block = f"--- Post {i} [r/{subreddit}] (score: {score}) ---\nTitle: {title}\n"
        if selftext.strip():
            block += f"Body: {selftext}\n"

        if total_chars + len(block) > limits.max_posts_chars:
            break

        lines.append(block)
        total_chars += len(block)

    return "\n".join(lines)


def _build_enrichment_context(state: ProductIntelligenceState) -> str:
    """Formata dados de enriquecimento de outros módulos."""
    sections: list[str] = []

    deep_dive = state.get("existing_deep_dive_products") or []
    if deep_dive:
        items = []
        for p in deep_dive[:30]:
            name = p.get("name", "unknown")
            cat = p.get("category", "")
            sent = p.get("sentiment", "")
            ctx = p.get("context", "")
            items.append(f"  - {name} ({cat}, {sent}): {ctx}")
        sections.append(
            "PREVIOUSLY IDENTIFIED PRODUCTS (from deep dive analyses):\n"
            + "\n".join(items)
        )

    tool_patterns = state.get("existing_tool_patterns") or []
    if tool_patterns:
        items = []
        for t in tool_patterns[:20]:
            tool = t.get("tool", "unknown")
            use_case = t.get("use_case", "")
            sat = t.get("satisfaction", "")
            pains = ", ".join(t.get("pain_points", [])[:3])
            items.append(
                f"  - {tool} (satisfaction: {sat}): {use_case}"
                + (f" | Pain points: {pains}" if pains else "")
            )
        sections.append(
            "TOOL USAGE PATTERNS (from behavioral analysis):\n" + "\n".join(items)
        )

    sol_requests = state.get("existing_solution_requests") or []
    if sol_requests:
        items = []
        for s in sol_requests[:20]:
            title = s.get("title", "")
            sub = s.get("subreddit", "")
            items.append(f"  - [{sub}] {title}")
        sections.append(
            "SOLUTION REQUESTS (posts seeking product recommendations):\n"
            + "\n".join(items)
        )

    if not sections:
        return "ENRICHMENT DATA: No additional data available from other analyses."

    return "ENRICHMENT DATA (from other analysis modules):\n\n" + "\n\n".join(sections)


def _parse_json_response(content: str) -> list[dict] | None:
    """Limpa e parseia resposta JSON do LLM."""
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3].strip()
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        logger.warning("Expected JSON array, got %s", type(result).__name__)
        return None
    except json.JSONDecodeError:
        logger.error("Failed to parse product intelligence JSON: %s", text[:500])
        return None


# ---------------------------------------------------------------------------
# Node 1: collect_context (sem LLM)
# ---------------------------------------------------------------------------
def collect_context(state: ProductIntelligenceState) -> dict:
    """Formata dados de enriquecimento de outros módulos como texto."""
    enrichment = _build_enrichment_context(state)
    return {"enrichment_context": enrichment}


# ---------------------------------------------------------------------------
# Node 2: extract_products (LLM)
# ---------------------------------------------------------------------------
def extract_products(state: ProductIntelligenceState) -> dict:
    """Extrai menções de produtos dos posts via LLM."""
    posts = state.get("posts") or []
    if not posts:
        logger.warning("No posts available for product extraction")
        return {"extracted_products": None}

    limits = _get_limits()
    posts_text = _build_posts_text(posts, limits)
    enrichment = state.get("enrichment_context") or ""

    llm = _get_llm()
    prompt = extract_products_prompt(
        audience_name=state["audience_name"],
        community_names=state["community_names"],
        posts_text=posts_text,
        enrichment_context=enrichment,
        total_posts=len(posts),
        language=state.get("language", "en"),
    )

    response = llm.invoke(prompt)
    content = extract_response_text(response)
    products = _parse_json_response(content)

    logger.info(
        "Extracted %d products from %d posts",
        len(products) if products else 0,
        len(posts),
    )
    return {"extracted_products": products}


# ---------------------------------------------------------------------------
# Node 3: aggregate_profiles (sem LLM)
# ---------------------------------------------------------------------------
def aggregate_profiles(state: ProductIntelligenceState) -> dict:
    """Normaliza nomes, merge duplicatas e constrói perfis finais."""
    extracted = state.get("extracted_products") or []
    if not extracted:
        return {"product_profiles": None}

    # Agrupar por nome normalizado
    grouped: dict[str, list[dict]] = defaultdict(list)
    for product in extracted:
        name = product.get("normalized_name") or product.get("product_name", "")
        key = name.strip().lower()
        if key:
            grouped[key].append(product)

    profiles: list[dict] = []
    for _norm_name, entries in grouped.items():
        # Escolher o nome canônico do entry com mais menções
        primary = max(entries, key=lambda e: e.get("total_mentions", 0))

        # Merge evidence_quotes de todas as entradas
        all_quotes: list[dict] = []
        all_communities: set[str] = set()
        all_use_cases: set[str] = set()
        all_positives: list[str] = []
        all_negatives: list[str] = []
        all_gaps: list[str] = []
        all_alternatives: list[dict] = []
        total_mentions = 0

        for entry in entries:
            total_mentions += entry.get("total_mentions", 0)
            for q in entry.get("evidence_quotes", []) or []:
                all_quotes.append(q)
            for c in entry.get("communities", []) or []:
                all_communities.add(c)
            for u in entry.get("use_cases", []) or []:
                all_use_cases.add(u)
            for p in entry.get("positive_aspects", []) or []:
                if p not in all_positives:
                    all_positives.append(p)
            for n in entry.get("negative_aspects", []) or []:
                if n not in all_negatives:
                    all_negatives.append(n)
            for g in entry.get("gaps", []) or []:
                if g not in all_gaps:
                    all_gaps.append(g)
            for a in entry.get("alternatives", []) or []:
                all_alternatives.append(a)

        # Dedup alternatives por nome normalizado
        seen_alts: set[str] = set()
        unique_alts: list[dict] = []
        for alt in all_alternatives:
            alt_key = alt.get("name", "").strip().lower()
            if alt_key and alt_key not in seen_alts:
                seen_alts.add(alt_key)
                unique_alts.append(alt)

        profile = {
            "product_name": primary.get("product_name", ""),
            "normalized_name": primary.get(
                "normalized_name",
                primary.get("product_name", "").strip().lower(),
            ),
            "category": primary.get("category", "tool"),
            "total_mentions": total_mentions,
            "sentiment_score": primary.get("sentiment_score"),
            "sentiment_label": primary.get("sentiment_label"),
            "trend_direction": primary.get("trend_direction"),
            "positive_aspects": all_positives[:5],
            "negative_aspects": all_negatives[:5],
            "gaps": all_gaps[:5],
            "alternatives": unique_alts[:5],
            "evidence_quotes": all_quotes[:5],
            "communities": sorted(all_communities),
            "use_cases": sorted(all_use_cases)[:5],
        }
        profiles.append(profile)

    # Ordenar por total_mentions desc
    profiles.sort(key=lambda p: p.get("total_mentions", 0), reverse=True)

    logger.info("Aggregated %d unique product profiles", len(profiles))
    return {"product_profiles": profiles}


# ---------------------------------------------------------------------------
# Node 4: detect_opportunities (LLM)
# ---------------------------------------------------------------------------
def detect_opportunities(state: ProductIntelligenceState) -> dict:
    """Detecta oportunidades de mercado a partir dos perfis."""
    profiles = state.get("product_profiles") or []
    if not profiles:
        return {"product_opportunities": []}

    # Formatar perfis como texto
    profile_lines: list[str] = []
    for p in profiles[:30]:
        name = p.get("product_name", "")
        cat = p.get("category", "")
        mentions = p.get("total_mentions", 0)
        sentiment = p.get("sentiment_label", "unknown")
        trend = p.get("trend_direction", "unknown")
        negatives = ", ".join(p.get("negative_aspects", [])[:3])
        gaps = ", ".join(p.get("gaps", [])[:3])
        profile_lines.append(
            f"- {name} ({cat}): {mentions} mentions, sentiment={sentiment}, trend={trend}"
            + (f"\n  Negatives: {negatives}" if negatives else "")
            + (f"\n  Gaps: {gaps}" if gaps else "")
        )
    product_profiles_text = "\n".join(profile_lines)

    # Formatar solution_requests
    sol_requests = state.get("existing_solution_requests") or []
    sol_lines: list[str] = []
    for s in sol_requests[:30]:
        title = s.get("title", "")
        sub = s.get("subreddit", "")
        sol_lines.append(f"- [{sub}] {title}")
    solution_requests_text = (
        "\n".join(sol_lines) if sol_lines else "No solution requests available."
    )

    llm = _get_llm()
    prompt = detect_opportunities_prompt(
        audience_name=state["audience_name"],
        community_names=state["community_names"],
        product_profiles_text=product_profiles_text,
        solution_requests_text=solution_requests_text,
        total_products=len(profiles),
        language=state.get("language", "en"),
    )

    response = llm.invoke(prompt)
    content = extract_response_text(response)
    opportunities = _parse_json_response(content)

    logger.info(
        "Detected %d market opportunities",
        len(opportunities) if opportunities else 0,
    )
    return {"product_opportunities": opportunities or []}


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------
def create_product_intelligence_agent():
    """Cria o grafo LangGraph para Product Intelligence."""
    workflow = StateGraph(ProductIntelligenceState)

    workflow.add_node("collect_context", collect_context)
    workflow.add_node("extract_products", extract_products)
    workflow.add_node("aggregate_profiles", aggregate_profiles)
    workflow.add_node("detect_opportunities", detect_opportunities)

    workflow.add_edge(START, "collect_context")
    workflow.add_edge("collect_context", "extract_products")
    workflow.add_edge("extract_products", "aggregate_profiles")
    workflow.add_edge("aggregate_profiles", "detect_opportunities")
    workflow.add_edge("detect_opportunities", END)

    return workflow.compile()
