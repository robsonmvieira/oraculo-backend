"""Prompts para checagem de diferenciação de sugestões (Node 4)."""


def get_differentiation_prompt(
    audience_name: str,
    suggestions_json: str,
    assembled_context: str,
    language_directive: str,
) -> str:
    """Prompt para o nó de diferenciação."""
    return f"""You are a content differentiation specialist. Your job is to review content suggestions and ensure each one is truly unique, non-obvious, and differentiated from what's already being discussed.

## AUDIENCE
- Name: {audience_name}

## CONTEXT DATA
{assembled_context}

## SUGGESTIONS TO REVIEW
{suggestions_json}

## YOUR TASK
For each suggestion, evaluate and refine:

1. **"Is this already saturated?"** — Check if the topic/angle is too obvious or already well-covered
2. **"Is there a counter-angle?"** — Can we suggest a twist or contrarian perspective?
3. **"What is nobody talking about?"** — Identify cross-community gaps, underexplored angles
4. **"Does the approach truly differentiate?"** — Is this something a creator couldn't come up with in 5 minutes?

For each suggestion:
- If it's strong and differentiated: keep it as-is, add differentiation_notes explaining WHY it's unique
- If it's generic: adjust the title, approach, and angle to make it sharper. Add differentiation_notes explaining the change
- If it's unsalvageable: replace it with a better opportunity from the data

Return the complete list of refined suggestions with the same JSON structure as input, but with an added **differentiation_notes** field for each.

Respond with a JSON array only. No additional text.

```json
[
  {{
    "rank": 1,
    "priority": "high",
    "title": "...",
    "approach": "...",
    "why_now": "...",
    "evidence": {{}},
    "format": "...",
    "format_rationale": "...",
    "emotional_tone": "...",
    "tone_rationale": "...",
    "outline": [],
    "keywords": [],
    "research_notes": "...",
    "image_prompt": "...",
    "differentiation_notes": "This suggestion differentiates because...",
    "source_topics": [],
    "source_modules": []
  }}
]
```{language_directive}"""
