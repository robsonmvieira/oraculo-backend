"""Estado do agente LangGraph para Product Intelligence."""

from __future__ import annotations

from typing import TypedDict


class ProductIntelligenceState(TypedDict):
    """Estado compartilhado entre os nós do grafo."""

    audience_name: str
    community_names: list[str]
    language: str

    # Entrada: posts vindos de ThemePosts
    posts: list[dict]

    # Entrada: dados de enriquecimento de outros módulos (opcional)
    existing_deep_dive_products: list[dict] | None
    existing_tool_patterns: list[dict] | None
    existing_solution_requests: list[dict] | None

    # Intermediário: contexto formatado de enriquecimento
    enrichment_context: str | None

    # Intermediário: produtos extraídos pelo LLM
    extracted_products: list[dict] | None

    # Saída final
    product_profiles: list[dict] | None
    product_opportunities: list[dict] | None
