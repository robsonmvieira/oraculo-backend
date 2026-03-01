"""Prompts para ranking de oportunidades de conteúdo (Node 2)."""


def get_rank_opportunities_prompt(
    audience_name: str,
    community_names_str: str,
    assembled_context: str,
    language_directive: str,
) -> str:
    """Prompt para o nó de ranking de oportunidades."""
    return f"""You are a content strategy analyst. Your job is to identify and rank content opportunities based on real data from Reddit communities.

## AUDIENCE
- Name: {audience_name}
- Communities: {community_names_str}

## AVAILABLE DATA (from multiple analytical modules)
{assembled_context}

## YOUR TASK
Cross-reference the signals above (topic growth, sentiment, unanswered questions, behavioral patterns, demand signals, theme timing) and identify 5-8 content opportunities ranked by potential impact.

For each opportunity, provide:
- **title**: A provisional title for the content piece (compelling hook)
- **score**: Impact score from 0 to 10 (based on growth + urgency + gap + demand)
- **justification**: Why this is a high-impact opportunity (cite specific data)
- **source_topics**: List of topic names that feed into this opportunity
- **signals**: List of signal types that support this (e.g., "growth_spike", "unanswered_questions", "new_topic", "pain_points", "demand_signal", "content_gap", "high_engagement")

## SCORING CRITERIA
- Growth spike (recent, strong growth) = +2
- Unanswered questions (gap in existing content) = +2
- Strong pain/anger sentiment = +1.5
- New topic (appeared recently) = +1.5
- Demand signals (explicit requests) = +1
- Cross-community gap (discussed in one but not others) = +1
- High engagement score = +1

## RULES
1. Only propose opportunities grounded in the data above. Do NOT invent data.
2. If data is limited, propose fewer but stronger opportunities.
3. Prioritize timely opportunities (new topics, growth spikes) over evergreen ones.
4. Each opportunity should have a unique angle — avoid overlapping suggestions.

Respond with a JSON array only. No additional text.

```json
[
  {{
    "title": "...",
    "score": 8.5,
    "justification": "...",
    "source_topics": ["Topic A", "Topic B"],
    "signals": ["growth_spike", "unanswered_questions"]
  }}
]
```{language_directive}"""
