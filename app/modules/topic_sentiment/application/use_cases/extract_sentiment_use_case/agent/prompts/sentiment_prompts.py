from app.modules.shared.application.helpers.language_directive import get_language_directive


def sentiment_analysis_prompt(
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

    prompt = f"""You are an expert sentiment analyst specializing in Reddit community discussions. Your task is to perform an in-depth emotional and sentiment analysis of a specific topic.

Audience: "{audience_name}"
Communities: {communities_str}
Topic: "{topic_name}"
Topic description: {topic_description}
Total posts analyzed: {total_posts}
Total comments analyzed: {total_comments}

Below are posts and their top comments related to this topic:

{posts_with_comments_text}

---

TASK: Perform a comprehensive sentiment analysis of this topic. Go beyond simple positive/negative classification — uncover the emotional drivers, tensions, pain points, and opportunities hidden in how people feel about this topic. You must produce a structured analysis in JSON format with the following sections:

1. **overall_sentiment**: The high-level sentiment summary:
   - "score": "positive", "negative", "neutral", or "mixed"
   - "positive_ratio": float 0-1
   - "negative_ratio": float 0-1
   - "neutral_ratio": float 0-1

2. **emotional_map**: Identify 4-8 distinct emotions present in the discussions. Go beyond positive/negative — detect enthusiasm, frustration, skepticism, curiosity, fear, hope, anger, confusion, excitement, resignation, etc. Each should have:
   - "emotion": Name of the emotion
   - "intensity": "high", "medium", or "low"
   - "percentage": float 0-1 (all percentages must sum to 1.0)
   - "example": A real quote or paraphrase from the data that exemplifies this emotion

3. **sentiment_by_community**: Break down sentiment per subreddit/community. Each should have:
   - "community": Community name with r/ prefix (e.g., "r/digital_marketing")
   - "positive": float 0-1
   - "negative": float 0-1
   - "neutral": float 0-1
   - "dominant_emotion": The most prevalent emotion in this community

4. **sentiment_by_subtopic**: Identify 3-8 subtopics/facets within the main topic and analyze sentiment for each. Each should have:
   - "subtopic": 2-4 word name of the subtopic
   - "sentiment": "positive", "negative", "neutral", or "mixed"
   - "score": float 0-1 (0 = very negative, 0.5 = neutral, 1 = very positive)
   - "key_driver": What primarily drives the sentiment for this subtopic

5. **sentiment_drivers**: Identify the root causes behind positive and negative sentiment:
   - "positive": Array of 3-6 drivers, each with:
     - "driver": What causes positive sentiment (2-5 words)
     - "frequency": "high", "medium", or "low"
     - "mentions": Estimated number of mentions
     - "example_quote": A real quote from the data
   - "negative": Array of 3-6 drivers, same structure

6. **tension_points**: Identify 2-5 topics where the community is polarized — significant disagreement between people. Each should have:
   - "topic": The polarizing subject (short phrase)
   - "for_ratio": float 0-1 (proportion supporting)
   - "against_ratio": float 0-1 (proportion opposing)
   - "intensity": "high", "medium", or "low" (how heated the debate is)
   - "summary": Brief summary of both sides

7. **pain_points**: Extract 3-8 specific frustrations, complaints, and unmet needs expressed by people. Each should have:
   - "pain": The frustration or problem (1 sentence)
   - "severity": "high", "medium", or "low"
   - "frequency": "high", "medium", or "low"
   - "communities": Array of communities where this pain appears
   - "verbatim": An actual quote from a post or comment that expresses this pain

8. **sentiment_opportunities**: Identify 3-6 opportunities that emerge from the sentiment analysis — where negative sentiment or pain points signal unmet market needs. Each should have:
   - "opportunity": Clear, actionable description
   - "based_on": Which pain points or sentiment patterns support this
   - "confidence": "high", "medium", or "low"
   - "target_audience": Who would benefit from addressing this

IMPORTANT:
- Base ALL analysis on the actual posts and comments provided. Do NOT invent data or quotes.
- If there isn't enough data for a section, provide fewer items rather than fabricating.
- Be specific — use real quotes, reference actual discussions, and name specific communities.
- All ratios within a section must sum to 1.0 where applicable (overall_sentiment ratios, emotional_map percentages, per-community ratios).
- Focus on the "why" behind sentiments, not just the "what". Drivers and root causes are more valuable than surface-level categorization.
- Pain points and verbatims should be as close to the original text as possible.

Respond ONLY with valid JSON. No markdown code blocks, no explanations outside the JSON.

Example structure:
{{"overall_sentiment": {{...}}, "emotional_map": [...], "sentiment_by_community": [...], "sentiment_by_subtopic": [...], "sentiment_drivers": {{...}}, "tension_points": [...], "pain_points": [...], "sentiment_opportunities": [...]}}"""

    return prompt + get_language_directive(language)
