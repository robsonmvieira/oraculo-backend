from app.modules.shared.application.helpers.language_directive import (
    get_language_directive,
)


def semantic_search_grouping_prompt(
    audience_name: str,
    community_names: list[str],
    query: str,
    posts_text: str,
    total_matched: int,
    language: str = "en",
) -> str:
    communities_str = ", ".join(f"r/{name}" for name in community_names)
    language_directive = get_language_directive(language)

    return f"""You are an expert analyst specialized in online community research.
Your task is to analyze Reddit posts that are semantically related to a user's search query
and group them into meaningful thematic patterns.

Audience: "{audience_name}"
Communities: {communities_str}

USER SEARCH QUERY:
"{query}"

MATCHED POSTS (ordered by semantic similarity to the query):
{posts_text}

Total matched posts: {total_matched}

---

INSTRUCTIONS:
1. First, write a concise summary (2-4 paragraphs) analyzing what these posts reveal
   in relation to the user's query. Focus on actionable insights, recurring themes,
   and the overall sentiment.

2. Then, group the posts into 3 to 8 thematic patterns based on their content
   and relevance to the query.

Respond in JSON format:
{{
  "summary": "Your analytical summary here...",
  "patterns": [
    {{
      "name": "Short descriptive name (5-10 words)",
      "emoji": "single emoji representing the theme",
      "description": "Brief 1-2 sentence description of this pattern",
      "post_ids": ["reddit_id_1", "reddit_id_2"]
    }}
  ]
}}

RULES:
- Summary: 2-4 paragraphs, data-driven, cite specific examples from the posts
- Create 3 to 8 patterns maximum
- Each pattern must have at least 1 post
- Each post_id must appear in EXACTLY ONE pattern
- Every post_id from the input should be assigned to a pattern
- Pattern names should be descriptive thematic phrases (5-10 words)
- Use a single emoji that best represents each pattern
- Order patterns by number of posts (most posts first)
- post_ids must match exactly the POST_ID values from the input
- Return ONLY the JSON object, no additional text
{language_directive}"""


def semantic_search_no_results_prompt(
    audience_name: str,
    community_names: list[str],
    query: str,
    language: str = "en",
) -> str:
    """Prompt for when no matching posts are found."""
    communities_str = ", ".join(f"r/{name}" for name in community_names)
    language_directive = get_language_directive(language)

    return f"""You are an expert analyst specialized in online community research.

Audience: "{audience_name}"
Communities: {communities_str}

The user searched for: "{query}"

Unfortunately, no posts were found that are semantically similar to this query
in the audience's communities.

Write a brief, helpful response (2-3 sentences) that:
1. Acknowledges no matching posts were found
2. Suggests why (e.g., topic might not be discussed in these communities)
3. Suggests a refined search query or alternative approach

Respond as plain text (not JSON).
{language_directive}"""
