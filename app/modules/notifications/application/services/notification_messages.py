"""Catálogo de traduções para mensagens de notificação do sistema.

Organizado por idioma → chave de mensagem → template com placeholders.
Fallback automático para inglês quando a tradução não existe.
"""

_CATALOG: dict[str, dict[str, str]] = {
    # ──────────────────────────────────────────────────────────
    # English (default / fallback)
    # ──────────────────────────────────────────────────────────
    "en": {
        # --- Analysis complete ---
        "topic_analysis_complete_title": "Topic Analysis Complete",
        "topic_analysis_complete_msg_audience": (
            "Topic analysis for audience '{audience_name}' is ready for viewing."
        ),
        "topic_analysis_complete_msg_topic": (
            "Topic analysis for topic '{topic_name}' is ready for viewing."
        ),
        "keyword_analysis_complete_title": "Keyword Analysis Complete",
        "keyword_analysis_complete_msg_audience": (
            "Keyword analysis for audience '{audience_name}' is ready for viewing."
        ),
        "keyword_analysis_complete_msg_topic": (
            "Keyword analysis for topic '{topic_name}' is ready for viewing."
        ),
        "deep_dive_complete_title": "Deep Dive Complete",
        "deep_dive_complete_msg_audience": (
            "Deep dive for audience '{audience_name}' is ready for viewing."
        ),
        "deep_dive_complete_msg_topic": (
            "Deep dive for topic '{topic_name}' is ready for viewing."
        ),
        "pattern_analysis_complete_title": "Pattern Analysis Complete",
        "pattern_analysis_complete_msg_audience": (
            "Pattern analysis for audience '{audience_name}' is ready for viewing."
        ),
        "pattern_analysis_complete_msg_topic": (
            "Pattern analysis for topic '{topic_name}' is ready for viewing."
        ),
        "behavioral_pattern_complete_title": "Behavioral Patterns Complete",
        "behavioral_pattern_complete_msg_audience": (
            "Behavioral pattern analysis for audience '{audience_name}' is ready for viewing."
        ),
        "behavioral_pattern_complete_msg_topic": (
            "Behavioral pattern analysis for topic '{topic_name}' is ready for viewing."
        ),
        "theme_analysis_complete_title": "Theme Analysis Complete",
        "theme_analysis_complete_msg_audience": (
            "Theme analysis for audience '{audience_name}' is ready for viewing."
        ),
        "theme_analysis_complete_msg_topic": (
            "Theme analysis for topic '{topic_name}' is ready for viewing."
        ),
        "intent_classification_complete_title": "Intent Classification Complete",
        "intent_classification_complete_msg_audience": (
            "Intent classification for audience '{audience_name}' is ready for viewing."
        ),
        "intent_classification_complete_msg_topic": (
            "Intent classification for topic '{topic_name}' is ready for viewing."
        ),
        "theme_summary_complete_title": "Theme Summary Complete",
        "theme_summary_complete_msg_audience": (
            "Theme summary for audience '{audience_name}' is ready for viewing."
        ),
        "theme_summary_complete_msg_topic": (
            "Theme summary for topic '{topic_name}' is ready for viewing."
        ),
        "youtube_validation_complete_title": "YouTube Validation Complete",
        "youtube_validation_complete_msg_audience": (
            "YouTube validation for audience '{audience_name}' is ready for viewing."
        ),
        "youtube_validation_complete_msg_topic": (
            "YouTube validation for topic '{topic_name}' is ready for viewing."
        ),
        "product_intelligence_complete_title": "Product Intelligence Complete",
        "product_intelligence_complete_msg_audience": (
            "Product intelligence for audience '{audience_name}' is ready for viewing."
        ),
        "product_intelligence_complete_msg_topic": (
            "Product intelligence for topic '{topic_name}' is ready for viewing."
        ),
        # --- Analysis failed ---
        "topic_analysis_failed_title": "Topic Analysis Failed",
        "topic_analysis_failed_msg_audience": (
            "Topic analysis for audience '{audience_name}' failed. Please try again."
        ),
        "topic_analysis_failed_msg_topic": (
            "Topic analysis for topic '{topic_name}' failed. Please try again."
        ),
        "keyword_analysis_failed_title": "Keyword Analysis Failed",
        "keyword_analysis_failed_msg_audience": (
            "Keyword analysis for audience '{audience_name}' failed. Please try again."
        ),
        "keyword_analysis_failed_msg_topic": (
            "Keyword analysis for topic '{topic_name}' failed. Please try again."
        ),
        "deep_dive_failed_title": "Deep Dive Failed",
        "deep_dive_failed_msg_audience": (
            "Deep dive for audience '{audience_name}' failed. Please try again."
        ),
        "deep_dive_failed_msg_topic": (
            "Deep dive for topic '{topic_name}' failed. Please try again."
        ),
        "pattern_analysis_failed_title": "Pattern Analysis Failed",
        "pattern_analysis_failed_msg_audience": (
            "Pattern analysis for audience '{audience_name}' failed. Please try again."
        ),
        "pattern_analysis_failed_msg_topic": (
            "Pattern analysis for topic '{topic_name}' failed. Please try again."
        ),
        "behavioral_pattern_failed_title": "Behavioral Patterns Failed",
        "behavioral_pattern_failed_msg_audience": (
            "Behavioral pattern analysis for audience '{audience_name}' failed. Please try again."
        ),
        "behavioral_pattern_failed_msg_topic": (
            "Behavioral pattern analysis for topic '{topic_name}' failed. Please try again."
        ),
        "theme_analysis_failed_title": "Theme Analysis Failed",
        "theme_analysis_failed_msg_audience": (
            "Theme analysis for audience '{audience_name}' failed. Please try again."
        ),
        "theme_analysis_failed_msg_topic": (
            "Theme analysis for topic '{topic_name}' failed. Please try again."
        ),
        "intent_classification_failed_title": "Intent Classification Failed",
        "intent_classification_failed_msg_audience": (
            "Intent classification for audience '{audience_name}' failed. Please try again."
        ),
        "intent_classification_failed_msg_topic": (
            "Intent classification for topic '{topic_name}' failed. Please try again."
        ),
        "theme_summary_failed_title": "Theme Summary Failed",
        "theme_summary_failed_msg_audience": (
            "Theme summary for audience '{audience_name}' failed. Please try again."
        ),
        "theme_summary_failed_msg_topic": (
            "Theme summary for topic '{topic_name}' failed. Please try again."
        ),
        "youtube_validation_failed_title": "YouTube Validation Failed",
        "youtube_validation_failed_msg_audience": (
            "YouTube validation for audience '{audience_name}' failed. Please try again."
        ),
        "youtube_validation_failed_msg_topic": (
            "YouTube validation for topic '{topic_name}' failed. Please try again."
        ),
        "product_intelligence_failed_title": "Product Intelligence Failed",
        "product_intelligence_failed_msg_audience": (
            "Product intelligence for audience '{audience_name}' failed. Please try again."
        ),
        "product_intelligence_failed_msg_topic": (
            "Product intelligence for topic '{topic_name}' failed. Please try again."
        ),
        # --- Communities ---
        "communities_updated_title": "Communities Updated",
        "communities_updated_msg": (
            "Audience communities updated: {added} added, {removed} removed."
        ),
        "communities_invalid_title": "Invalid Communities Removed",
        "communities_invalid_msg": (
            "The following communities were not found on Reddit "
            "and have been removed: {names}"
        ),
        # --- Content suggestions ---
        "content_suggestions_ready_title": "Content Suggestions Ready",
        "content_suggestions_ready_msg": (
            "{count} content suggestions generated for audience '{audience_name}'."
        ),
        "content_suggestions_failed_title": "Content Suggestions Failed",
        "content_suggestions_failed_msg": (
            "Failed to generate suggestions for audience '{audience_name}'. "
            "Please try again."
        ),
        # --- Content production ---
        "content_production_ready_title": "Content Ready",
        "content_production_ready_msg": ("Content '{title}' is ready for {platforms}."),
        "content_production_failed_title": "Content Production Failed",
        "content_production_failed_msg": (
            "Failed to produce content. Please try again."
        ),
    },
    # ──────────────────────────────────────────────────────────
    # Brazilian Portuguese
    # ──────────────────────────────────────────────────────────
    "pt-BR": {
        # --- Analysis complete ---
        "topic_analysis_complete_title": "Análise de Tópicos Concluída",
        "topic_analysis_complete_msg_audience": (
            "A análise de tópicos da audiência '{audience_name}' "
            "está pronta para visualização."
        ),
        "topic_analysis_complete_msg_topic": (
            "A análise de tópicos do tópico '{topic_name}' "
            "está pronta para visualização."
        ),
        "keyword_analysis_complete_title": "Análise de Keywords Concluída",
        "keyword_analysis_complete_msg_audience": (
            "A análise de keywords da audiência '{audience_name}' "
            "está pronta para visualização."
        ),
        "keyword_analysis_complete_msg_topic": (
            "A análise de keywords do tópico '{topic_name}' "
            "está pronta para visualização."
        ),
        "deep_dive_complete_title": "Deep Dive Concluído",
        "deep_dive_complete_msg_audience": (
            "O deep dive da audiência '{audience_name}' está pronto para visualização."
        ),
        "deep_dive_complete_msg_topic": (
            "O deep dive do tópico '{topic_name}' está pronto para visualização."
        ),
        "pattern_analysis_complete_title": "Análise de Padrões Concluída",
        "pattern_analysis_complete_msg_audience": (
            "A análise de padrões da audiência '{audience_name}' "
            "está pronta para visualização."
        ),
        "pattern_analysis_complete_msg_topic": (
            "A análise de padrões do tópico '{topic_name}' "
            "está pronta para visualização."
        ),
        "behavioral_pattern_complete_title": "Padrões Comportamentais Concluídos",
        "behavioral_pattern_complete_msg_audience": (
            "A análise de padrões comportamentais da audiência '{audience_name}' "
            "está pronta para visualização."
        ),
        "behavioral_pattern_complete_msg_topic": (
            "A análise de padrões comportamentais do tópico '{topic_name}' "
            "está pronta para visualização."
        ),
        "theme_analysis_complete_title": "Análise de Temas Concluída",
        "theme_analysis_complete_msg_audience": (
            "A análise de temas da audiência '{audience_name}' "
            "está pronta para visualização."
        ),
        "theme_analysis_complete_msg_topic": (
            "A análise de temas do tópico '{topic_name}' está pronta para visualização."
        ),
        "intent_classification_complete_title": "Classificação de Intenções Concluída",
        "intent_classification_complete_msg_audience": (
            "A classificação de intenções da audiência '{audience_name}' "
            "está pronta para visualização."
        ),
        "intent_classification_complete_msg_topic": (
            "A classificação de intenções do tópico '{topic_name}' "
            "está pronta para visualização."
        ),
        "theme_summary_complete_title": "Resumo de Temas Concluído",
        "theme_summary_complete_msg_audience": (
            "O resumo de temas da audiência '{audience_name}' "
            "está pronto para visualização."
        ),
        "theme_summary_complete_msg_topic": (
            "O resumo de temas do tópico '{topic_name}' está pronto para visualização."
        ),
        "youtube_validation_complete_title": "Validação do YouTube Concluída",
        "youtube_validation_complete_msg_audience": (
            "A validação do YouTube da audiência '{audience_name}' "
            "está pronta para visualização."
        ),
        "youtube_validation_complete_msg_topic": (
            "A validação do YouTube do tópico '{topic_name}' "
            "está pronta para visualização."
        ),
        "product_intelligence_complete_title": "Inteligência de Produto Concluída",
        "product_intelligence_complete_msg_audience": (
            "A análise de inteligência de produto da audiência '{audience_name}' "
            "está pronta para visualização."
        ),
        "product_intelligence_complete_msg_topic": (
            "A análise de inteligência de produto do tópico '{topic_name}' "
            "está pronta para visualização."
        ),
        # --- Analysis failed ---
        "topic_analysis_failed_title": "Falha na Análise de Tópicos",
        "topic_analysis_failed_msg_audience": (
            "A análise de tópicos da audiência '{audience_name}' falhou. "
            "Tente novamente."
        ),
        "topic_analysis_failed_msg_topic": (
            "A análise de tópicos do tópico '{topic_name}' falhou. Tente novamente."
        ),
        "keyword_analysis_failed_title": "Falha na Análise de Keywords",
        "keyword_analysis_failed_msg_audience": (
            "A análise de keywords da audiência '{audience_name}' falhou. "
            "Tente novamente."
        ),
        "keyword_analysis_failed_msg_topic": (
            "A análise de keywords do tópico '{topic_name}' falhou. Tente novamente."
        ),
        "deep_dive_failed_title": "Falha no Deep Dive",
        "deep_dive_failed_msg_audience": (
            "O deep dive da audiência '{audience_name}' falhou. Tente novamente."
        ),
        "deep_dive_failed_msg_topic": (
            "O deep dive do tópico '{topic_name}' falhou. Tente novamente."
        ),
        "pattern_analysis_failed_title": "Falha na Análise de Padrões",
        "pattern_analysis_failed_msg_audience": (
            "A análise de padrões da audiência '{audience_name}' falhou. "
            "Tente novamente."
        ),
        "pattern_analysis_failed_msg_topic": (
            "A análise de padrões do tópico '{topic_name}' falhou. Tente novamente."
        ),
        "behavioral_pattern_failed_title": "Falha nos Padrões Comportamentais",
        "behavioral_pattern_failed_msg_audience": (
            "A análise de padrões comportamentais da audiência '{audience_name}' "
            "falhou. Tente novamente."
        ),
        "behavioral_pattern_failed_msg_topic": (
            "A análise de padrões comportamentais do tópico '{topic_name}' "
            "falhou. Tente novamente."
        ),
        "theme_analysis_failed_title": "Falha na Análise de Temas",
        "theme_analysis_failed_msg_audience": (
            "A análise de temas da audiência '{audience_name}' falhou. Tente novamente."
        ),
        "theme_analysis_failed_msg_topic": (
            "A análise de temas do tópico '{topic_name}' falhou. Tente novamente."
        ),
        "intent_classification_failed_title": "Falha na Classificação de Intenções",
        "intent_classification_failed_msg_audience": (
            "A classificação de intenções da audiência '{audience_name}' falhou. "
            "Tente novamente."
        ),
        "intent_classification_failed_msg_topic": (
            "A classificação de intenções do tópico '{topic_name}' falhou. "
            "Tente novamente."
        ),
        "theme_summary_failed_title": "Falha no Resumo de Temas",
        "theme_summary_failed_msg_audience": (
            "O resumo de temas da audiência '{audience_name}' falhou. Tente novamente."
        ),
        "theme_summary_failed_msg_topic": (
            "O resumo de temas do tópico '{topic_name}' falhou. Tente novamente."
        ),
        "youtube_validation_failed_title": "Falha na Validação do YouTube",
        "youtube_validation_failed_msg_audience": (
            "A validação do YouTube da audiência '{audience_name}' falhou. "
            "Tente novamente."
        ),
        "youtube_validation_failed_msg_topic": (
            "A validação do YouTube do tópico '{topic_name}' falhou. Tente novamente."
        ),
        "product_intelligence_failed_title": "Falha na Inteligência de Produto",
        "product_intelligence_failed_msg_audience": (
            "A análise de inteligência de produto da audiência '{audience_name}' "
            "falhou. Tente novamente."
        ),
        "product_intelligence_failed_msg_topic": (
            "A análise de inteligência de produto do tópico '{topic_name}' "
            "falhou. Tente novamente."
        ),
        # --- Communities ---
        "communities_updated_title": "Comunidades Atualizadas",
        "communities_updated_msg": (
            "As comunidades da audiência foram atualizadas: "
            "{added} adicionadas, {removed} removidas."
        ),
        "communities_invalid_title": "Comunidades Inválidas Removidas",
        "communities_invalid_msg": (
            "As seguintes comunidades não foram encontradas no Reddit "
            "e foram removidas: {names}"
        ),
        # --- Content suggestions ---
        "content_suggestions_ready_title": "Sugestões de Conteúdo Prontas",
        "content_suggestions_ready_msg": (
            "{count} sugestões de conteúdo geradas para a audiência '{audience_name}'."
        ),
        "content_suggestions_failed_title": "Falha nas Sugestões de Conteúdo",
        "content_suggestions_failed_msg": (
            "Não foi possível gerar sugestões para a audiência "
            "'{audience_name}'. Tente novamente."
        ),
        # --- Content production ---
        "content_production_ready_title": "Conteúdo Pronto",
        "content_production_ready_msg": (
            "O conteúdo '{title}' está pronto para {platforms}."
        ),
        "content_production_failed_title": "Falha na Produção de Conteúdo",
        "content_production_failed_msg": (
            "Não foi possível produzir o conteúdo. Tente novamente."
        ),
    },
}

DEFAULT_LANGUAGE = "en"


def t(key: str, language: str, **params: object) -> str:
    """Retorna a mensagem traduzida para o idioma, com fallback para inglês.

    Args:
        key: Chave da mensagem no catálogo (ex: "topic_analysis_complete_title").
        language: Código do idioma (ex: "pt-BR", "en").
        **params: Valores para interpolação nos templates (ex: audience_name="Foo").

    Returns:
        Mensagem traduzida e interpolada. Retorna a chave se não encontrada.
    """
    catalog = _CATALOG.get(language, _CATALOG[DEFAULT_LANGUAGE])
    template = catalog.get(key, _CATALOG[DEFAULT_LANGUAGE].get(key, key))
    return template.format(**params) if params else template
