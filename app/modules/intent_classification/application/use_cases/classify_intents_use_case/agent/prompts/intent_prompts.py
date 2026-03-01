"""Prompts para o agente de classificação de intenção."""


def get_classify_intents_prompt(
    audience_name: str,
    communities_str: str,
    period_start: str,
    period_end: str,
    posts_batch_text: str,
    language_directive: str = "",
) -> str:
    """Prompt para classificação de intenção de posts em batch."""
    return f"""You are an expert in analyzing online community discussions and classifying user intent.

Audience: "{audience_name}"
Communities: {communities_str}
Period: {period_start} to {period_end}

Below is a batch of posts from these communities. For each post, classify its PRIMARY intent
(and optionally a SECONDARY intent) into one of these categories:

CATEGORIES:
- advice_request: People asking for advice, recommendations, guidance, or opinions
- pain_and_anger: People expressing frustration, pain, disappointment, anger, or venting
- solution_request: People actively looking for tools, products, services, or specific solutions
- self_promotion: People promoting their own products, services, content, or creations
- ideas: People suggesting ideas, proposing improvements, brainstorming, or imagining possibilities
- news: People sharing news, events, announcements, PSAs, or current developments

POSTS:
{posts_batch_text}

---

Respond in JSON format. For each post, provide:
[
  {{
    "post_id": "reddit_post_id",
    "primary_intent": "category_name",
    "secondary_intent": "category_name_or_null",
    "confidence": "high|medium|low"
  }}
]

RULES:
- Every post MUST have a primary_intent from the 6 categories above
- secondary_intent is optional — only include if clearly applicable, otherwise use null
- A post about a bad experience asking for advice = primary: "pain_and_anger", secondary: "advice_request"
- When in doubt between two categories, pick the one that reflects the author's MAIN purpose
- Use "high" confidence when the intent is unambiguous, "medium" when reasonable, "low" when unclear
- Return ONLY the JSON array, no additional text
{language_directive}"""


def get_aggregate_intents_prompt(
    audience_name: str,
    period_start: str,
    period_end: str,
    intent_counts_json: str,
    language_directive: str = "",
) -> str:
    """Prompt para gerar descrições de cada categoria de intenção."""
    return f"""You are a business analyst summarizing community intent patterns for a product manager.

Audience: "{audience_name}"
Period: {period_start} to {period_end}

Here is the intent classification summary:

{intent_counts_json}

For each intent category, write a brief (1-2 sentences) description that explains:
- What people in this category typically want
- What specific sub-themes or patterns you noticed

Respond in JSON:
[
  {{"category": "advice_request", "description": "People are primarily seeking guidance on..."}},
  {{"category": "pain_and_anger", "description": "..."}},
  ...
]

RULES:
- Include only categories that have posts (post_count > 0)
- Descriptions should be actionable — help a product manager spot opportunities
- Return ONLY the JSON array, no additional text
{language_directive}"""


def get_analyze_pain_anger_prompt(
    audience_name: str,
    period_start: str,
    period_end: str,
    posts_text: str,
    total_posts: int,
    language_directive: str = "",
) -> str:
    """Prompt para análise holística de sentimentos e tópicos em posts pain_and_anger."""
    return f"""You are an expert psychologist and community analyst specializing in understanding emotional expressions in online communities.

Audience: "{audience_name}"
Period: {period_start} to {period_end}
Total pain_and_anger posts: {total_posts}

Below are ALL posts classified as "pain_and_anger" from this audience's communities.
Your task is to analyze them holistically and identify:

1. **Sentiment subcategories**: What specific emotions are people expressing? (e.g., frustration, anger, disappointment, anxiety, sadness, concern, helplessness, etc.)
2. **Topic keywords**: What specific subjects/themes are causing these emotions? Use single words. (e.g., pricing, support, quality, shipping, dog, behavior, etc.)

POSTS:
{posts_text}

---

Respond in JSON format:
{{
  "subcategories": {{
    "emotion_name": count,
    "emotion_name": count
  }},
  "topic_keywords": {{
    "keyword": count,
    "keyword": count
  }}
}}

RULES:
- subcategories: Return up to 10 emotions, sorted by count descending
- topic_keywords: Return up to 10 single-word topics, sorted by count descending
- Each count represents how many posts express that emotion or relate to that topic
- A single post can contribute to multiple emotions or topics
- Use lowercase for all keys
- Emotions should be specific (use "frustration" not "negative", use "anxiety" not "bad")
- Topics should be single words that capture the core subject (use "pricing" not "high prices")
- The sum of subcategory counts may exceed total_posts (one post can express multiple emotions)
- Return ONLY the JSON object, no additional text
{language_directive}"""
