from app.modules.shared.application.helpers.language_directive import get_language_directive


def deep_dive_analysis_prompt(
    topic_name: str,
    topic_description: str,
    audience_name: str,
    community_names: list[str],
    posts_with_comments_text: str,
    total_posts: int,
    total_comments: int,
    language: str = "en",
) -> str:
    communities_str = ", ".join(f"r/{name}" for name in community_names)

    prompt = f"""You are an expert Reddit analyst performing a deep dive analysis on a specific topic.

Audience: "{audience_name}"
Communities: {communities_str}
Topic: "{topic_name}"
Topic description: {topic_description}
Total posts analyzed: {total_posts}
Total comments analyzed: {total_comments}

Below are posts and their top comments related to this topic:

{posts_with_comments_text}

---

TASK: Perform a comprehensive deep dive analysis of this topic. You must produce a structured analysis in JSON format with the following sections:

1. **summary**: Write 2-3 paragraphs summarizing what this topic is about, why it matters to this audience, and what the key takeaways are. Be specific — reference actual discussions and patterns you see in the data.

2. **subtopics**: Identify 3-10 distinct facets/subtopics within this theme. Each subtopic should have:
   - "name": 2-4 word name
   - "description": One sentence explaining this subtopic
   - "post_count": Estimated number of posts related to this subtopic

3. **common_questions**: Identify 3-8 frequently asked questions within this topic. Each should have:
   - "question": The actual question (as people phrase it)
   - "frequency": "high", "medium", or "low"
   - "example_context": A brief excerpt from a real post/comment showing this question

4. **sentiment**: Analyze the overall sentiment around this topic:
   - "overall": "positive", "negative", "neutral", or "mixed"
   - "positive_ratio": float 0-1
   - "negative_ratio": float 0-1
   - "neutral_ratio": float 0-1
   - "highlights": Array of 3-6 notable sentiment examples, each with:
     - "text": The quote or paraphrased text
     - "sentiment": "positive", "negative", or "neutral"
     - "source": The subreddit it came from (e.g., "r/SocialMediaMarketing")

5. **mentioned_products**: List tools, services, brands, or products mentioned in discussions. Each should have:
   - "name": Product/tool name
   - "category": "tool", "service", "brand", "platform", or "resource"
   - "sentiment": "positive", "negative", "neutral", or "mixed"
   - "mention_count": Estimated number of mentions
   - "context": Brief context of how/why it's mentioned

   If no products are mentioned, return an empty array.

6. **actionable_insights**: Extract 3-6 actionable insights from the analysis. Each should have:
   - "insight": Clear, actionable statement
   - "type": "opportunity" (unmet need), "gap" (missing content/solution), "trend" (emerging pattern), or "warning" (risk/issue)
   - "confidence": "high", "medium", or "low"

IMPORTANT:
- Base ALL analysis on the actual posts and comments provided. Do NOT invent data.
- If there isn't enough data for a section, provide fewer items rather than fabricating.
- Be specific — reference actual content patterns, not generic observations.
- Sentiment ratios must sum to 1.0.

Respond ONLY with valid JSON. No markdown code blocks, no explanations outside the JSON.

Example structure:
{{"summary": "...", "subtopics": [...], "common_questions": [...], "sentiment": {{...}}, "mentioned_products": [...], "actionable_insights": [...]}}"""

    return prompt + get_language_directive(language)


def select_representative_posts_prompt(
    topic_name: str,
    posts_text: str,
    language: str = "en",
) -> str:
    prompt = f"""You are selecting the most representative posts for the topic "{topic_name}".

Below are posts related to this topic:

{posts_text}

---

TASK: Select 5-10 posts that best represent this topic. Choose posts that:
- Cover different aspects/subtopics
- Have high engagement (score, comments)
- Provide clear examples of the topic in action
- Represent diverse perspectives

For each selected post, provide:
- "title": The post title
- "subreddit": The subreddit name (without r/)
- "score": The post score
- "permalink": The post permalink
- "excerpt": A 1-2 sentence excerpt that captures why this post is representative

Respond ONLY with a valid JSON array. No markdown code blocks.

Example:
[{{"title": "...", "subreddit": "...", "score": 123, "permalink": "/r/sub/comments/...", "excerpt": "..."}}]"""

    return prompt + get_language_directive(language)
