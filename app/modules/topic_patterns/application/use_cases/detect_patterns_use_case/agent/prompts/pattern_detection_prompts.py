def pattern_detection_prompt(
    audience_name: str,
    community_names: list[str],
    topics_text: str,
    posts_with_comments_text: str,
    total_topics: int,
    total_posts: int,
    total_comments: int,
) -> str:
    communities_str = ", ".join(f"r/{name}" for name in community_names)

    return f"""You are an expert Reddit analyst specializing in cross-topic pattern detection.

Audience: "{audience_name}"
Communities: {communities_str}
Total topics analyzed: {total_topics}
Total posts analyzed: {total_posts}
Total comments analyzed: {total_comments}

Below are all topics identified for this audience:

{topics_text}

---

Below are posts and their top comments from the audience's communities:

{posts_with_comments_text}

---

TASK: Analyze ALL topics and posts together to detect cross-topic patterns that would be hard to identify by looking at individual topics. You must produce a structured analysis in JSON format with the following sections:

1. **summary**: Write 2-3 paragraphs summarizing the most important cross-topic patterns you found. What themes connect different topics? What overarching narrative emerges? Be specific and reference actual patterns.

2. **co_occurrences**: Identify 3-8 pairs or groups of topics that frequently appear together in the same discussions or communities. Each should have:
   - "topics": Array of 2-3 topic names that co-occur
   - "frequency": "high", "medium", or "low"
   - "context": Brief explanation of how/why these topics appear together

3. **unanswered_questions**: Identify 3-8 questions that are frequently asked across topics but rarely get satisfactory answers. These represent opportunities. Each should have:
   - "question": The actual question (as people phrase it)
   - "frequency": "high", "medium", or "low"
   - "communities": Array of communities where this question appears
   - "opportunity": What product, content, or service could address this gap

4. **emerging_opinions**: Identify 3-6 minority opinions or positions that appear to be gaining traction. Each should have:
   - "opinion": The opinion or position
   - "support_level": "growing", "established", or "nascent"
   - "evidence": Brief evidence from the data (quotes, upvote patterns, etc.)
   - "communities": Array of communities where this opinion appears

5. **cross_community_gaps**: Identify 3-6 topics or themes that are heavily discussed in some communities but completely absent in others where they would be relevant. Each should have:
   - "topic": The topic or theme
   - "discussed_in": Array of communities where it's discussed
   - "missing_in": Array of communities where it's absent but relevant
   - "opportunity": Why this gap matters and what could fill it

6. **content_opportunities**: Extract 3-8 specific content or product opportunities derived from all the patterns above. Each should have:
   - "opportunity": Clear, actionable description
   - "type": "content" (blog post, guide, course), "product" (tool, SaaS), or "service" (consulting, agency)
   - "confidence": "high", "medium", or "low"
   - "based_on": Which patterns or data points support this opportunity

IMPORTANT:
- This is CROSS-TOPIC analysis. Look for connections BETWEEN topics, not just within them.
- Base ALL analysis on the actual topics, posts and comments provided. Do NOT invent data.
- If there isn't enough data for a section, provide fewer items rather than fabricating.
- Be specific — reference actual content patterns, topic names, and community names.
- Focus on patterns that would be hard to spot by analyzing topics individually.

Respond ONLY with valid JSON. No markdown code blocks, no explanations outside the JSON.

Example structure:
{{"summary": "...", "co_occurrences": [...], "unanswered_questions": [...], "emerging_opinions": [...], "cross_community_gaps": [...], "content_opportunities": [...]}}"""
