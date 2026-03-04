"""YouTube-specific context limits per LLM provider.

Gemini (2M tokens) allows aggressive collection and unified analysis.
OpenAI (128K tokens) requires conservative collection and per-topic analysis.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from app.modules.shared.application.services.llm_factory import _detect_provider


@dataclass(frozen=True)
class YouTubeContextLimits:
    """Limites de contexto específicos para coleta e análise YouTube."""

    max_videos_per_topic: int
    max_comments_per_video: int
    max_transcript_chars: int
    max_videos_with_transcript: int
    max_total_analysis_chars: int
    analysis_mode: str  # "unified" (1 call) or "per_topic" (N calls)


_YOUTUBE_GEMINI_DEFAULTS = YouTubeContextLimits(
    max_videos_per_topic=20,
    max_comments_per_video=100,
    max_transcript_chars=50_000,
    max_videos_with_transcript=10,
    max_total_analysis_chars=1_200_000,
    analysis_mode="unified",
)

_YOUTUBE_OPENAI_DEFAULTS = YouTubeContextLimits(
    max_videos_per_topic=5,
    max_comments_per_video=30,
    max_transcript_chars=10_000,
    max_videos_with_transcript=3,
    max_total_analysis_chars=80_000,
    analysis_mode="per_topic",
)


def get_youtube_context_limits(
    model_env_var: str = "YOUTUBE_VALIDATION_MODEL_NAME",
    default_model: str = "gpt-5-nano-2025-08-07",
) -> YouTubeContextLimits:
    """Retorna limites de contexto YouTube baseados no provider do modelo configurado."""
    model_name = os.getenv(model_env_var, os.getenv("MODEL_NAME", default_model))
    provider = _detect_provider(model_name)
    if provider == "gemini":
        return _YOUTUBE_GEMINI_DEFAULTS
    return _YOUTUBE_OPENAI_DEFAULTS
