"""Prompts para geração de estratégia de conteúdo detalhada (Node 3)."""


def get_content_strategy_prompt(
    audience_name: str,
    community_names_str: str,
    assembled_context: str,
    opportunities_json: str,
    language_directive: str,
) -> str:
    """Prompt para o nó de estratégia de conteúdo."""
    return f"""You are an expert content strategist. Your job is to transform ranked content opportunities into detailed, actionable content suggestions grounded in real community data.

## AUDIENCE
- Name: {audience_name}
- Communities: {community_names_str}

## AVAILABLE DATA
{assembled_context}

## RANKED OPPORTUNITIES (from previous analysis)
{opportunities_json}

## YOUR TASK
For the top 3-5 opportunities (highest scores), generate a complete content suggestion with every field below.

For each suggestion, provide:
- **rank**: Position (1 = best opportunity)
- **priority**: "high", "medium", or "low"
- **title**: Proposed content title (compelling hook using the audience's own language)
- **approach**: Unique angle/approach. What makes this different from generic content on the topic. Be specific.
- **why_now**: Why this content matters RIGHT NOW. Cite temporal signals (growth spikes, new topics, weekly themes).
- **evidence**: Object with real data supporting this suggestion:
  - growth: {{topic, growth_percentage, trend}}
  - unanswered_questions: [list of real questions from the data]
  - pain_points: [{{pain, severity, frequency}}]
  - workarounds: [{{workaround, frequency}}]
  - sentiment: {{dominant_emotion, intensity, positive_ratio}}
- **format**: One of: "thread", "carrossel", "artigo", "video_script", "newsletter", "infographic"
- **format_rationale**: Why this format, based on intent distribution data
- **emotional_tone**: One of: "educativo", "urgente", "empatico", "provocativo", "inspirador", "analitico"
- **tone_rationale**: Why this tone, based on sentiment analysis data
- **outline**: Array of content structure items [{{slide/item: N, content: "..."}}]
- **keywords**: SEO keywords from the audience's real vocabulary
- **research_notes**: What to research/verify before creating the content
- **image_prompt**: Detailed instruction for AI image generation (describe visual style, elements, mood)
- **source_topics**: [{{topic_id: "...", topic_name: "...", growth_percentage: N}}]
- **source_modules**: List of analytical modules that contributed data

## PRINCIPLES
1. ALWAYS cite evidence — "Based on 47 mentions of frustration with pricing in r/dogs..."
2. Propose counter-intuitive angles — if the obvious take is "X is good", suggest "the 3 problems nobody talks about with X"
3. Reference real data — tool names, specific workarounds, real quotes when available
4. Format based on intent — if 60% are advice_request → tutorial/guide. If 40% pain_and_anger → validation thread
5. Indicate timing — new weekly theme = urgency ("post this week"). Stable theme = evergreen
6. NEVER invent data — if there's not enough data for a suggestion, generate fewer but stronger ones
7. Use the audience's language — terms and expressions they actually use (from keywords and real posts)

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
    "format": "carrossel",
    "format_rationale": "...",
    "emotional_tone": "educativo",
    "tone_rationale": "...",
    "outline": [],
    "keywords": [],
    "research_notes": "...",
    "image_prompt": "...",
    "source_topics": [],
    "source_modules": []
  }}
]
```{language_directive}"""
