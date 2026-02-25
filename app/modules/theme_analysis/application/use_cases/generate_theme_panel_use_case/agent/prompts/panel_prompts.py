"""Prompts para o agente de extração de subcategorias do painel."""


def get_extract_subcategories_prompt(
    audience_name: str,
    theme_name: str,
    time_window: str,
    period_start: str,
    period_end: str,
    posts_text: str,
    language_directive: str = "",
) -> str:
    """Prompt para extração de subcategorias de um tema."""
    return f"""You are a data analyst categorizing online discussions into meaningful subcategories.

Audience: "{audience_name}"
Theme: "{theme_name}"
Period: {time_window} ({period_start} to {period_end})

Below are posts belonging to this theme:

{posts_text}

---

TASK: Identify 3-8 subcategories that describe the main FACETS of this theme.

Subcategories should represent:
- Emotional facets (e.g., "Frustration", "Celebration", "Concern")
- Activity facets (e.g., "Questions", "Recommendations", "Debates")
- Thematic facets (e.g., "Health-related", "Cost-related", "Training-related")

For each subcategory:
1. Give it a clear, single-word or short name (1-3 words)
2. Count how many posts fit this subcategory
3. Write a brief description (1 sentence)

A post can belong to multiple subcategories.

Respond in JSON array format:
[
  {{"name": "Frustration", "count": 15, "description": "Posts expressing frustration about costs or services"}},
  {{"name": "Questions", "count": 32, "description": "Posts asking direct questions seeking specific answers"}}
]

RULES:
- Return ONLY the JSON array, no additional text
- Do not wrap in markdown code fences
- Order by count descending
- Minimum 3, maximum 8 subcategories

{language_directive}"""
