"""Shared LLM factory with multi-provider support and context limit profiles.

Detects the provider from the model name prefix:
- ``gemini-*`` -> Google Gemini (ChatGoogleGenerativeAI)
- ``claude-*`` -> Anthropic Claude (ChatAnthropic)
- everything else -> OpenAI (ChatOpenAI)

Each agent can request provider-specific context limits via ``get_context_limits``
so that agents running on Gemini's 2M-token window automatically fetch and process
more data from the Reddit API without manual configuration.
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass

from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Context limits
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContextLimits:
    """Configuration for context-window utilisation limits."""

    max_posts_chars: int
    max_comment_length: int
    comments_per_post: int
    max_selftext_length: int
    top_posts_for_comments: int
    comments_per_post_fetch: int


_OPENAI_DEFAULTS = ContextLimits(
    max_posts_chars=100_000,
    max_comment_length=500,
    comments_per_post=5,
    max_selftext_length=600,
    top_posts_for_comments=10,
    comments_per_post_fetch=20,
)

_GEMINI_DEFAULTS = ContextLimits(
    max_posts_chars=800_000,
    max_comment_length=2000,
    comments_per_post=20,
    max_selftext_length=2000,
    top_posts_for_comments=40,
    comments_per_post_fetch=50,
)


# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------


def _detect_provider(model_name: str) -> str:
    """Return ``'gemini'``, ``'anthropic'`` or ``'openai'`` from *model_name*."""
    lower = model_name.lower()
    if lower.startswith("gemini-"):
        return "gemini"
    if lower.startswith("claude-"):
        return "anthropic"
    return "openai"


# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------


def create_llm(
    model_env_var: str = "MODEL_NAME",
    default_model: str = "gpt-5-nano-2025-08-07",
    temperature: float = 0,
    **kwargs,
) -> BaseChatModel:
    """Create an LLM instance based on the model name from the environment.

    The provider is detected automatically from the model name prefix.

    Args:
        model_env_var: Environment variable that holds the model name.
        default_model: Fallback when the env var is unset.
        temperature: Sampling temperature.
        **kwargs: Extra kwargs forwarded to the chat-model constructor.
    """
    model_name = os.getenv(model_env_var, default_model)
    provider = _detect_provider(model_name)

    logger.info("LLM factory: env=%s model=%s provider=%s", model_env_var, model_name, provider)

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            **kwargs,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model_name,
            temperature=temperature,
            **kwargs,
        )

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        **kwargs,
    )


def extract_response_text(response) -> str:
    """Extract text content from an LLM response, normalizing across providers.

    Gemini may return response.content as a list of parts instead of a plain
    string.  This helper guarantees a plain ``str`` is returned regardless of
    the provider used.
    """
    content = response.content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.append(part.get("text", ""))
            else:
                parts.append(str(part))
        return "".join(parts).strip()
    return str(content).strip()


# ---------------------------------------------------------------------------
# Context limits factory
# ---------------------------------------------------------------------------


def get_context_limits(
    model_env_var: str = "MODEL_NAME",
    default_model: str = "gpt-5-nano-2025-08-07",
    openai_overrides: dict | None = None,
    gemini_overrides: dict | None = None,
) -> ContextLimits:
    """Return context limits appropriate for the configured model's provider.

    Each agent can customise provider-specific defaults via override dicts.

    Args:
        model_env_var: Environment variable that holds the model name.
        default_model: Fallback when the env var is unset.
        openai_overrides: Field overrides applied when provider is OpenAI.
        gemini_overrides: Field overrides applied when provider is Gemini.
    """
    model_name = os.getenv(model_env_var, default_model)
    provider = _detect_provider(model_name)

    if provider == "gemini":
        base = _GEMINI_DEFAULTS
        overrides = gemini_overrides or {}
    else:
        base = _OPENAI_DEFAULTS
        overrides = openai_overrides or {}

    if overrides:
        merged = {**asdict(base), **overrides}
        return ContextLimits(**merged)

    return base
