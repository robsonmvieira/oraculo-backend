"""Estado do agente de producao de conteudo."""

from typing import TypedDict


class PlatformDraft(TypedDict):
    platform: str
    hooks: list[dict]
    full_draft: str
    narrative_arc: str
    cta: str
    platform_notes: str
    hashtags: list[str]
    image_aspect_ratio: str


class ContentProductionState(TypedDict):
    # Inputs
    suggestion: dict
    target_platforms: list[str]
    audience_name: str
    audience_description: str | None
    community_names: list[str]
    language: str

    # Node 1 output
    platform_drafts: list[PlatformDraft]

    # Node 2 output (final)
    refined_drafts: list[PlatformDraft]
