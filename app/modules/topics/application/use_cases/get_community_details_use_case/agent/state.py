# 1. Definir o State - dados que fluem pelo grafo
from typing import TypedDict


class CommunityAnalyzerState(TypedDict):
    """Estado do agente"""

    title: str  # Título da comunidade
    public_description: str  # Descrição pública
    derived_terms: list[str]  # Termos derivados gerados pelo LLM
