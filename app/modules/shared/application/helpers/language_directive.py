"""Helper para injetar diretiva de idioma nos prompts dos agentes LLM."""

SUPPORTED_LANGUAGES = {
    "en": "English",
    "pt-BR": "Brazilian Portuguese",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
}


def get_language_directive(language_code: str) -> str:
    """Retorna bloco de instrução de idioma para concatenar ao final dos prompts.

    Se o idioma for inglês, retorna string vazia (comportamento padrão).
    """
    if language_code == "en":
        return ""

    language_name = SUPPORTED_LANGUAGES.get(language_code, language_code)

    return (
        f"\n\nLANGUAGE INSTRUCTION: Write ALL text content "
        f"(summaries, descriptions, insights, questions, analysis, "
        f"recommendations, evidence excerpts, context) in {language_name}. "
        f"Keep all JSON keys, field names, and enum values "
        f"(like 'high', 'medium', 'low', 'positive', 'negative', 'neutral', "
        f"'opportunity', 'gap', 'trend', 'warning', 'satisfied', 'mixed', "
        f"'dissatisfied', 'common', 'moderate', 'rare', 'early', 'growing', "
        f"'established', 'tool', 'service', 'brand', 'platform', 'resource') "
        f"in English exactly as specified in the format above."
    )
