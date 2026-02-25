"""Prompts para o agente de extração de temas temporais."""


def get_extract_themes_prompt(
    audience_name: str,
    communities_str: str,
    time_window: str,
    period_start: str,
    period_end: str,
    total_posts: int,
    posts_text: str,
    language_directive: str = "",
) -> str:
    """Prompt do nó 1: extração de temas a partir dos posts filtrados."""
    return f"""You are an expert Reddit analyst specializing in temporal trend detection.

Audience: "{audience_name}"
Communities: {communities_str}
Time window: {time_window} ({period_start} to {period_end})
Total posts in window: {total_posts}

Below are the titles and text from posts in these communities during this period:

{posts_text}

---

TASK: Identify the most prominent discussion themes from this {time_window} period.

For each theme:
1. Name (2-5 words, descriptive of the theme)
2. Count how many posts relate to this theme
3. Calculate average score and average comments for posts in this theme
4. List the top subreddits where this theme appears, with post counts and avg scores
5. Extract the 3-5 most representative/engaged posts (title, subreddit, score, permalink)
6. List 5-10 keywords that characterize this theme

Focus on TEMPORAL relevance — what makes this {time_window} period unique?
Highlight themes that are spiking, emerging, or unusually active.

Return between 3 and 8 themes, ranked by engagement potential.

Respond in JSON format:
[
  {{
    "name": "...",
    "post_count": N,
    "avg_score": N.N,
    "avg_comments": N.N,
    "top_subreddits": [{{"name": "...", "post_count": N, "avg_score": N.N}}],
    "representative_posts": [{{"title": "...", "subreddit": "...", "score": N, "permalink": "..."}}],
    "keywords": ["...", "..."]
  }}
]

IMPORTANT: Return ONLY valid JSON array. No markdown, no explanation.{language_directive}"""


def get_generate_summary_prompt(
    audience_name: str,
    communities_str: str,
    time_window: str,
    period_start: str,
    period_end: str,
    themes_json: str,
    language_directive: str = "",
) -> str:
    """Prompt do nó 2: geração de resumo narrativo por tema."""
    return f"""You are a newsletter writer summarizing Reddit discussions for a community manager.

Audience: "{audience_name}"
Time window: This {time_window} ({period_start} to {period_end})
Communities: {communities_str}

Here are the themes identified for this period:

{themes_json}

---

TASK: Write a 2-3 sentence narrative summary for EACH theme.

The summary should:
- Be written in the style of a newsletter intro paragraph
- Mention specific subreddits and topics naturally
- Capture the MOOD and ENERGY of the discussions
- Explain WHY this theme was relevant this {time_window}

Respond in JSON:
[
  {{"theme_name": "...", "summary": "..."}}
]

IMPORTANT: Return ONLY valid JSON array. No markdown, no explanation.{language_directive}"""
