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


def get_pain_patterns_prompt(
    audience_name: str,
    period_start: str,
    period_end: str,
    posts_text: str,
    total_posts: int,
    language_directive: str = "",
    has_comments: bool = False,
) -> str:
    """Prompt para agrupar posts pain_and_anger em padrões de dor comportamentais."""
    comments_context = ""
    comments_json_fields = ""
    comments_rules = ""

    if has_comments:
        comments_context = """
Note: Some posts include their top community comments (sorted by score). Use these comments to better understand the true severity and breadth of each pain pattern."""

        comments_json_fields = """,
    "validation_score": "high|medium|low — based on how many commenters validate/echo the same pain",
    "suggested_coping": ["solution or coping strategy mentioned in comments"]"""

        comments_rules = """
- validation_score: Analyze comments to determine if other users validate the same pain. "high" = multiple commenters agree/echo ("same here", "I deal with this too"), "medium" = some agreement, "low" = little or no agreement in comments
- suggested_coping: Extract any solutions, workarounds, or coping strategies mentioned by commenters. Return empty array if none found
- Use comments to better judge which patterns represent widespread community pain vs isolated complaints"""

    return f"""You are an expert psychologist and community analyst. Your task is to group pain & anger posts into behavioral pain patterns — recurring themes that reveal what the audience is truly struggling with.

Audience: "{audience_name}"
Period: {period_start} to {period_end}
Total pain_and_anger posts: {total_posts}

Below are posts classified as "pain_and_anger" from this audience's communities, including their body text for richer context.{comments_context}

POSTS:
{posts_text}

---

Group these posts into 3 to 8 behavioral pain patterns. Each pattern should represent a distinct, recurring theme of pain or frustration.

Respond in JSON format:
[
  {{
    "name": "Short descriptive name of the pain pattern (5-10 words)",
    "emoji": "single emoji representing the emotional tone",
    "post_ids": ["id1", "id2", "id3"]{comments_json_fields}
  }}
]

RULES:
- Create 3 to 8 patterns maximum
- Each pattern must have at least 2 posts (if total posts < 6, patterns with 1 post are acceptable)
- Each post_id must appear in EXACTLY ONE pattern — no duplicates across patterns
- Every post_id from the input should be assigned to a pattern
- Pattern names should be descriptive behavioral/emotional phrases (5-10 words)
- Use a single emoji that best represents the emotional tone of the pattern
- Order patterns by number of posts (most posts first)
- post_ids must match exactly the POST_ID values from the input
- Return ONLY the JSON array, no additional text{comments_rules}
{language_directive}"""


def get_analyze_solution_requests_prompt(
    audience_name: str,
    period_start: str,
    period_end: str,
    posts_text: str,
    total_posts: int,
    language_directive: str = "",
) -> str:
    """Prompt para análise holística de tipos de solução e tópicos em posts solution_request."""
    return f"""You are an expert product strategist and community analyst specializing in understanding what solutions people are actively seeking in online communities.

Audience: "{audience_name}"
Period: {period_start} to {period_end}
Total solution_request posts: {total_posts}

Below are ALL posts classified as "solution_request" from this audience's communities.
Your task is to analyze them holistically and identify:

1. **Solution type subcategories**: What kinds of solutions are people looking for? (e.g., tools, automation, templates, integrations, frameworks, metrics, workflows, platforms, tutorials, APIs, etc.)
2. **Topic keywords**: What specific subjects are people seeking solutions for? Use single words. (e.g., scheduling, analytics, CRM, email, SEO, reporting, dashboard, etc.)

POSTS:
{posts_text}

---

Respond in JSON format:
{{
  "subcategories": {{
    "solution_type": count,
    "solution_type": count
  }},
  "topic_keywords": {{
    "keyword": count,
    "keyword": count
  }}
}}

RULES:
- subcategories: Return up to 10 solution types, sorted by count descending
- topic_keywords: Return up to 10 single-word topics, sorted by count descending
- Each count represents how many posts seek that type of solution or relate to that topic
- A single post can contribute to multiple solution types or topics
- Use lowercase for all keys
- Solution types should be specific (use "automation" not "technology", use "templates" not "resources")
- Topics should be single words that capture the core subject (use "scheduling" not "scheduling tools")
- The sum of subcategory counts may exceed total_posts (one post can seek multiple solution types)
- Return ONLY the JSON object, no additional text
{language_directive}"""


def get_solution_patterns_prompt(
    audience_name: str,
    period_start: str,
    period_end: str,
    posts_text: str,
    total_posts: int,
    language_directive: str = "",
    has_comments: bool = False,
) -> str:
    """Prompt para agrupar posts solution_request em padrões de busca de solução."""
    comments_context = ""
    comments_json_fields = ""
    comments_rules = ""

    if has_comments:
        comments_context = """
Note: Some posts include their top community comments (sorted by score). Use these comments to identify which tools, services, and products the community actually recommends — not just what the OP is asking for."""

        comments_json_fields = """,
    "recommended_solutions": ["specific tool, service, or product recommended in comments"],
    "community_consensus": "strong|moderate|weak|divided — level of agreement on best solution"
"""

        comments_rules = """
- recommended_solutions: Extract specific tools, libraries, services, or products recommended by commenters. Return empty array if none found
- community_consensus: Based on comment agreement — "strong" = most commenters agree on a solution, "moderate" = some agreement, "weak" = few recommendations, "divided" = conflicting opinions
- Use comments to distinguish between what people ask for and what the community actually recommends"""

    return f"""You are an expert product strategist and community analyst. Your task is to group solution request posts into solution-seeking patterns — recurring themes that reveal what the audience is actively trying to solve or build.

Audience: "{audience_name}"
Period: {period_start} to {period_end}
Total solution_request posts: {total_posts}

Below are posts classified as "solution_request" from this audience's communities, including their body text for richer context.{comments_context}

POSTS:
{posts_text}

---

Group these posts into 3 to 8 solution-seeking patterns. Each pattern should represent a distinct, recurring need or type of solution being sought.

Respond in JSON format:
[
  {{
    "name": "Short descriptive name of the solution pattern (5-10 words)",
    "emoji": "single emoji representing the type of solution sought",
    "post_ids": ["id1", "id2", "id3"]{comments_json_fields}
  }}
]

RULES:
- Create 3 to 8 patterns maximum
- Each pattern must have at least 2 posts (if total posts < 6, patterns with 1 post are acceptable)
- Each post_id must appear in EXACTLY ONE pattern — no duplicates across patterns
- Every post_id from the input should be assigned to a pattern
- Pattern names should be descriptive solution-seeking phrases (5-10 words)
- Use a single emoji that best represents the type of solution (e.g., 🔧 tools, 📊 analytics, 🤖 automation, 📋 templates)
- Order patterns by number of posts (most posts first)
- post_ids must match exactly the POST_ID values from the input
- Return ONLY the JSON array, no additional text{comments_rules}
{language_directive}"""


def get_analyze_advice_requests_prompt(
    audience_name: str,
    period_start: str,
    period_end: str,
    posts_text: str,
    total_posts: int,
    language_directive: str = "",
) -> str:
    """Prompt para análise holística de tipos de conselho e tópicos em posts advice_request."""
    return f"""You are an expert community analyst specializing in understanding what guidance, recommendations, and expert opinions people seek in online communities.

Audience: "{audience_name}"
Period: {period_start} to {period_end}
Total advice_request posts: {total_posts}

Below are ALL posts classified as "advice_request" from this audience's communities.
Your task is to analyze them holistically and identify:

1. **Advice type subcategories**: What kinds of advice are people looking for? (e.g., career, strategy, beginner, comparison, best_practices, recommendation, troubleshooting, scaling, optimization, workflow, budgeting, hiring, etc.)
2. **Topic keywords**: What specific subjects are people seeking advice about? Use single words. (e.g., marketing, pricing, hiring, SEO, content, branding, analytics, freelancing, etc.)

POSTS:
{posts_text}

---

Respond in JSON format:
{{
  "subcategories": {{
    "advice_type": count,
    "advice_type": count
  }},
  "topic_keywords": {{
    "keyword": count,
    "keyword": count
  }}
}}

RULES:
- subcategories: Return up to 10 advice types, sorted by count descending
- topic_keywords: Return up to 10 single-word topics, sorted by count descending
- Each count represents how many posts seek that type of advice or relate to that topic
- A single post can contribute to multiple advice types or topics
- Use lowercase for all keys
- Advice types should be specific (use "career" not "life", use "comparison" not "questions")
- Topics should be single words that capture the core subject (use "pricing" not "pricing strategy")
- The sum of subcategory counts may exceed total_posts (one post can seek multiple advice types)
- Return ONLY the JSON object, no additional text
{language_directive}"""


def get_advice_patterns_prompt(
    audience_name: str,
    period_start: str,
    period_end: str,
    posts_text: str,
    total_posts: int,
    language_directive: str = "",
) -> str:
    """Prompt para agrupar posts advice_request em padrões de busca de conselho."""
    return f"""You are an expert community analyst. Your task is to group advice request posts into advice-seeking patterns — recurring themes that reveal what guidance and recommendations the audience is actively looking for.

Audience: "{audience_name}"
Period: {period_start} to {period_end}
Total advice_request posts: {total_posts}

Below are posts classified as "advice_request" from this audience's communities, including their body text for richer context.

POSTS:
{posts_text}

---

Group these posts into 3 to 8 advice-seeking patterns. Each pattern should represent a distinct, recurring type of guidance or recommendation being sought.

Respond in JSON format:
[
  {{
    "name": "Short descriptive name of the advice pattern (5-10 words)",
    "emoji": "single emoji representing the type of advice sought",
    "post_ids": ["id1", "id2", "id3"]
  }}
]

RULES:
- Create 3 to 8 patterns maximum
- Each pattern must have at least 2 posts (if total posts < 6, patterns with 1 post are acceptable)
- Each post_id must appear in EXACTLY ONE pattern — no duplicates across patterns
- Every post_id from the input should be assigned to a pattern
- Pattern names should be descriptive advice-seeking phrases (5-10 words)
- Use a single emoji that best represents the advice type (e.g., 🎯 strategy, 📈 growth, 💼 career, 🤔 comparison, 📚 learning, 💡 best practices)
- Order patterns by number of posts (most posts first)
- post_ids must match exactly the POST_ID values from the input
- Return ONLY the JSON array, no additional text
{language_directive}"""


def get_analyze_ideas_prompt(
    audience_name: str,
    period_start: str,
    period_end: str,
    posts_text: str,
    total_posts: int,
    language_directive: str = "",
) -> str:
    """Prompt para análise holística de tipos de ideias e tópicos em posts ideas."""
    return f"""You are an expert community analyst specializing in understanding innovation signals, feature requests, product ideas, and creative suggestions shared in online communities.

Audience: "{audience_name}"
Period: {period_start} to {period_end}
Total ideas posts: {total_posts}

Below are ALL posts classified as "ideas" from this audience's communities.
Your task is to analyze them holistically and identify:

1. **Idea type subcategories**: What kinds of ideas are people proposing? (e.g., feature_request, product_idea, improvement, workflow_optimization, integration, new_concept, business_model, ux_redesign, automation, open_source, pricing_model, community_feature, etc.)
2. **Topic keywords**: What specific subjects are the ideas about? Use single words. (e.g., automation, dashboard, analytics, pricing, onboarding, mobile, api, collaboration, templates, scheduling, etc.)

POSTS:
{posts_text}

---

Respond in JSON format:
{{
  "subcategories": {{
    "idea_type": count,
    "idea_type": count
  }},
  "topic_keywords": {{
    "keyword": count,
    "keyword": count
  }}
}}

RULES:
- subcategories: Return up to 10 idea types, sorted by count descending
- topic_keywords: Return up to 10 single-word topics, sorted by count descending
- Each count represents how many posts propose that type of idea or relate to that topic
- A single post can contribute to multiple idea types or topics
- Use lowercase for all keys
- Idea types should be specific (use "feature_request" not "suggestion", use "ux_redesign" not "design")
- Topics should be single words that capture the core subject (use "automation" not "automation tools")
- The sum of subcategory counts may exceed total_posts (one post can propose multiple idea types)
- Return ONLY the JSON object, no additional text
{language_directive}"""


def get_ideas_patterns_prompt(
    audience_name: str,
    period_start: str,
    period_end: str,
    posts_text: str,
    total_posts: int,
    language_directive: str = "",
    has_comments: bool = False,
) -> str:
    """Prompt para agrupar posts ideas em padrões de inovação/sugestão."""
    comments_instruction = ""
    if has_comments:
        comments_instruction = """

IMPORTANT — THREAD COMMENTS ANALYSIS:
Some posts include top community comments (marked with 💬 COMMENTS). Use them to:
1. Assess **community_reception**: How the community reacted to the idea — "enthusiastic" (strong support, many want it), "positive" (general agreement), "mixed" (divided opinions), "skeptical" (doubts about feasibility/value)
2. Extract **refinements**: Concrete improvements or variations suggested by commenters that make the idea better
3. Extract **feasibility_notes**: Any technical or practical considerations mentioned by the community about implementing the idea
- If comments are present, include "community_reception", "refinements", and "feasibility_notes" fields in each pattern"""

    return f"""You are an expert community analyst. Your task is to group idea posts into innovation patterns — recurring themes that reveal what improvements, features, and creative concepts the audience is actively proposing and discussing.

Audience: "{audience_name}"
Period: {period_start} to {period_end}
Total ideas posts: {total_posts}

Below are posts classified as "ideas" from this audience's communities, including their body text for richer context.
{comments_instruction}

POSTS:
{posts_text}

---

Group these posts into 3 to 8 innovation/idea patterns. Each pattern should represent a distinct, recurring type of idea or suggestion being proposed.

Respond in JSON format:
[
  {{
    "name": "Short descriptive name of the idea pattern (5-10 words)",
    "emoji": "single emoji representing the type of idea",
    "post_ids": ["id1", "id2", "id3"]{', "community_reception": "enthusiastic|positive|mixed|skeptical", "refinements": ["suggestion1", "suggestion2"], "feasibility_notes": ["note1", "note2"]' if has_comments else ''}
  }}
]

RULES:
- Create 3 to 8 patterns maximum
- Each pattern must have at least 2 posts (if total posts < 6, patterns with 1 post are acceptable)
- Each post_id must appear in EXACTLY ONE pattern — no duplicates across patterns
- Every post_id from the input should be assigned to a pattern
- Pattern names should be descriptive innovation phrases (5-10 words)
- Use a single emoji that best represents the idea type (e.g., 💡 new concept, 🚀 feature request, 🔧 improvement, 🔄 workflow, 🤖 automation, 📊 analytics, 🎨 design, 🔌 integration)
- Order patterns by number of posts (most posts first)
- post_ids must match exactly the POST_ID values from the input
- Return ONLY the JSON array, no additional text
{language_directive}"""
