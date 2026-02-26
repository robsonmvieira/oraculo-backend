"""Regras e thresholds para geracao de alertas."""

# --- Thresholds de crescimento ---
GROWTH_SPIKE_WARNING_THRESHOLD = 50.0  # >50% = warning
GROWTH_SPIKE_CRITICAL_THRESHOLD = 100.0  # >100% = critical

# --- Thresholds de frequencia para topicos novos ---
NEW_TOPIC_WARNING_MIN_FREQUENCY = 5  # mention_frequency >= 5 = warning
NEW_TOPIC_WARNING_MIN_COMMUNITIES = 2  # precisa aparecer em 2+ comunidades

# --- Thresholds de engagement para temas novos ---
NEW_THEME_WARNING_ENGAGEMENT = 5.0  # engagement_score >= 5 = warning
NEW_THEME_CRITICAL_ENGAGEMENT = 8.0  # engagement_score >= 8 = critical


def classify_growth_severity(growth_pct: float) -> str | None:
    """Retorna severity baseado no crescimento, ou None se abaixo do threshold."""
    if growth_pct >= GROWTH_SPIKE_CRITICAL_THRESHOLD:
        return "critical"
    if growth_pct >= GROWTH_SPIKE_WARNING_THRESHOLD:
        return "warning"
    return None


def classify_new_topic_severity(
    mention_frequency: float | None,
    community_count: int,
) -> str:
    """Retorna severity para um topico novo."""
    freq = mention_frequency or 0
    if (
        freq >= NEW_TOPIC_WARNING_MIN_FREQUENCY
        and community_count >= NEW_TOPIC_WARNING_MIN_COMMUNITIES
    ):
        return "warning"
    return "info"


def classify_new_theme_severity(engagement_score: float | None) -> str:
    """Retorna severity para um tema novo."""
    score = engagement_score or 0
    if score >= NEW_THEME_CRITICAL_ENGAGEMENT:
        return "critical"
    if score >= NEW_THEME_WARNING_ENGAGEMENT:
        return "warning"
    return "info"
