"""Estado do agente de extração de subcategorias do painel."""

from typing import TypedDict


class SubcategoryItem(TypedDict):
    """Subcategoria extraída pelo agente."""

    name: str
    count: int
    description: str


class ThemePanelState(TypedDict):
    """Estado do grafo de geração de dados do painel."""

    # Inputs
    audience_name: str
    theme_name: str
    time_window: str
    period_start: str
    period_end: str
    language: str
    posts_text: str

    # Output
    subcategories: list[SubcategoryItem] | None
