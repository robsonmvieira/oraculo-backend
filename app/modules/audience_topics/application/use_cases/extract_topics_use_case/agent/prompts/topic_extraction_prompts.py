from app.modules.shared.application.helpers.language_directive import get_language_directive


def extract_topics_prompt(
    audience_name: str,
    audience_description: str | None,
    community_names: list[str],
    posts_text: str,
    total_posts: int,
    language: str = "en",
) -> str:
    communities_str = ", ".join(f"r/{name}" for name in community_names)
    desc_line = f"\nAudience description: {audience_description}" if audience_description else ""

    prompt = f"""You are an expert Reddit analyst specializing in trend detection and topic extraction.

Audience: "{audience_name}"{desc_line}
Communities: {communities_str}
Total posts analyzed: {total_posts}

Below are the titles and text from recent posts across these communities:

{posts_text}

---

TASK: Identify the most discussed and trending topics across these communities.

For each topic you identify:
1. Give it a clear, concise name (2-4 words)
2. Write a one-sentence description explaining the topic in context of this audience
3. Estimate how frequently this topic is mentioned: provide a number and period (day/week/month)
4. Count how many posts relate to this topic
5. List which communities discuss it and how many posts per community

Extract up to 200 topics, ranked by relevance and frequency.

IMPORTANT: Focus on recurring THEMES, not individual posts. Group similar discussions together.
Examples of good topics: "Health issues", "Training tips", "Product recommendations", "Budget concerns"
Examples of bad topics: "John's post about his dog" (too specific), "Random" (too vague)

Respond in this exact format, one topic per line:
NAME|DESCRIPTION|FREQUENCY_NUMBER|FREQUENCY_PERIOD|POST_COUNT|COMMUNITIES

Where COMMUNITIES is a semicolon-separated list of "subreddit_name:count"

Example line:
Health issues|Physical or mental conditions affecting pets that require attention|3|month|15|DogAdvice:10;CatAdvice:5

Do NOT include any other text, headers, or numbering. Just the pipe-delimited lines."""

    return prompt + get_language_directive(language)


def estimate_growth_prompt(
    topics_text: str,
    audience_name: str,
    language: str = "en",
) -> str:
    prompt = f"""You are an expert in Reddit trend analysis.

Audience: "{audience_name}"

Below are topics extracted from recent community discussions, with their mention frequency:

{topics_text}

---

TASK: Estimate the growth percentage for each topic.

Growth means how much MORE this topic is being discussed compared to its usual baseline.
Consider:
- Higher frequency + more communities = likely growing
- Niche topics appearing across multiple communities = strong growth signal
- Common/generic topics = lower growth unless unusually frequent

Assign a growth percentage between 0% and 500%:
- 0-50%: Stable, normal discussion levels
- 50-100%: Moderate growth, gaining traction
- 100-200%: Strong growth, clearly trending
- 200-500%: Viral growth, major trend

Respond with one line per topic in this exact format:
TOPIC_NAME|GROWTH_PERCENTAGE

Example:
Health issues|400
Training tips|150

Do NOT include any other text. Just the pipe-delimited lines."""

    return prompt + get_language_directive(language)
