from app.modules.shared.application.helpers.language_directive import (
    get_language_directive,
)


def unified_validation_prompt(
    audience_name: str,
    topics_text: str,
    total_topics: int,
    total_videos: int,
    total_comments: int,
    language: str = "en",
) -> str:
    """Prompt para análise unificada cross-platform (Gemini — todos os tópicos em 1 chamada)."""
    prompt = f"""You are an expert cross-platform analyst specializing in Reddit and YouTube audience intelligence.

Audience: "{audience_name}"
Total topics analyzed: {total_topics}
Total YouTube videos collected: {total_videos}
Total YouTube comments analyzed: {total_comments}

Below is the cross-platform data for each topic. For each topic you have:
- Reddit data: topic description, post count, community count, communities
- YouTube data: videos with metadata (views, likes, duration), comments, and transcripts

{topics_text}

---

TASK: Perform a comprehensive cross-platform validation comparing Reddit discussions with YouTube content for each topic. Produce a structured JSON with:

1. **topics**: An array where each element analyzes one topic with:
   - "topic_name": The topic name
   - "traction_score": 0-10 scale measuring how well this Reddit topic performs on YouTube (0 = no presence, 10 = massive presence)
   - "youtube_video_count": Number of YouTube videos found
   - "avg_views": Average views across found videos
   - "sentiment_reddit": Overall Reddit sentiment ("positive", "negative", "neutral", "mixed", "curious", "divided")
   - "sentiment_youtube": Overall YouTube sentiment (from comments + video tone)
   - "sentiment_divergence": 1-2 sentences explaining how/why sentiments differ between platforms (empty string if aligned)
   - "content_gap": true if topic is discussed on Reddit but underrepresented on YouTube
   - "content_gap_detail": Explanation of the gap (empty string if no gap)
   - "content_saturated": true if YouTube already has extensive coverage
   - "product_mentions": Array of products mentioned cross-platform, each with:
     - "product": Product name
     - "reddit_sentiment": Sentiment on Reddit
     - "youtube_sentiment": Sentiment on YouTube
     - "confidence": "high", "medium", or "low"
   - "top_videos": Top 3-5 most relevant videos, each with:
     - "title": Video title
     - "video_id": YouTube video ID
     - "views": View count
     - "likes": Like count
     - "comments_analyzed": Number of comments analyzed
   - "audience_overlap_score": 0-10 scale (are Reddit and YouTube discussing this topic with similar perspectives?)
   - "opportunity_insights": Array of 1-3 actionable insights specific to this topic

2. **cross_platform_summary**: An object with:
   - "total_topics_with_traction": Number of topics with traction_score >= 5
   - "avg_traction_score": Average traction_score across all topics
   - "content_gaps_found": Number of topics with content_gap = true
   - "key_findings": Array of 3-5 high-level findings from the cross-platform comparison
   - "best_opportunity": The single best cross-platform opportunity identified
   - "biggest_divergence": The topic with the biggest sentiment divergence between platforms

IMPORTANT:
- Base ALL analysis on the actual data provided. Do NOT invent data.
- If a topic has no YouTube data, set traction_score to 0 and note the absence.
- Be specific — reference actual video titles, comment patterns, and Reddit discussions.
- When comparing sentiments, explain WHY they differ (platform demographics, content format, etc).

Respond ONLY with valid JSON. No markdown code blocks, no explanations outside the JSON.

Example structure:
{{"topics": [...], "cross_platform_summary": {{...}}}}"""

    return prompt + get_language_directive(language)


def per_topic_validation_prompt(
    audience_name: str,
    topic_name: str,
    topic_text: str,
    language: str = "en",
) -> str:
    """Prompt para análise por tópico (OpenAI — 1 tópico por chamada)."""
    prompt = f"""You are an expert cross-platform analyst comparing Reddit and YouTube data for a specific topic.

Audience: "{audience_name}"
Topic: "{topic_name}"

Below is the cross-platform data for this topic:
{topic_text}

---

TASK: Analyze this topic's cross-platform presence. Return a JSON object with:
- "topic_name": "{topic_name}"
- "traction_score": 0-10 scale (YouTube presence for this Reddit topic)
- "youtube_video_count": Number of YouTube videos found
- "avg_views": Average views
- "sentiment_reddit": Reddit sentiment
- "sentiment_youtube": YouTube sentiment (from comments + transcripts)
- "sentiment_divergence": How sentiments differ (empty string if aligned)
- "content_gap": true/false
- "content_gap_detail": Gap explanation (empty string if no gap)
- "content_saturated": true/false
- "product_mentions": [{{ "product": str, "reddit_sentiment": str, "youtube_sentiment": str, "confidence": str }}]
- "top_videos": [{{ "title": str, "video_id": str, "views": int, "likes": int, "comments_analyzed": int }}]
- "audience_overlap_score": 0-10
- "opportunity_insights": [str]

IMPORTANT: Base ALL analysis on actual data. Respond ONLY with valid JSON.

Example: {{"topic_name": "...", "traction_score": 7.5, ...}}"""

    return prompt + get_language_directive(language)


def summary_prompt(
    audience_name: str,
    analysis_result_text: str,
    language: str = "en",
) -> str:
    """Prompt para gerar resumo executivo da análise cross-platform."""
    prompt = f"""You are summarizing a cross-platform Reddit vs YouTube validation for the audience "{audience_name}".

Here is the full analysis result:
{analysis_result_text}

---

TASK: Generate an executive summary JSON with:
- "topics_analyzed": Total number of topics
- "topics_with_youtube_traction": Number with traction_score >= 5
- "content_gaps_found": Number of content gaps
- "avg_traction_score": Average traction score (1 decimal)
- "total_videos_analyzed": Total videos across all topics
- "total_comments_analyzed": Total comments analyzed
- "headline": A 1-sentence headline summarizing the key finding
- "key_opportunities": Top 3 opportunities (array of strings)
- "risk_factors": Top 2 risk factors or warnings (array of strings)

Respond ONLY with valid JSON."""

    return prompt + get_language_directive(language)
