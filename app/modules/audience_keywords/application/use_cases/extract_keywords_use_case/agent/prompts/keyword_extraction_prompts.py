from app.modules.shared.application.helpers.language_directive import get_language_directive


def extract_keywords_prompt(
    audience_name: str,
    audience_description: str | None,
    community_names: list[str],
    community_descriptions: list[str],
    topics_summary: str | None,
    language: str = "en",
) -> str:
    communities_str = ", ".join(f"r/{name}" for name in community_names)
    desc_line = f"\nAudience description: {audience_description}" if audience_description else ""

    descriptions_block = ""
    if community_descriptions:
        desc_lines = []
        for name, desc in zip(community_names, community_descriptions):
            if desc:
                desc_lines.append(f"- r/{name}: {desc}")
        if desc_lines:
            descriptions_block = "\n\nCommunity descriptions:\n" + "\n".join(desc_lines)

    topics_block = ""
    if topics_summary:
        topics_block = f"\n\nTrending topics already identified in this audience:\n{topics_summary}"

    prompt = f"""You are an expert Reddit analyst specializing in audience research and keyword discovery.

Audience: "{audience_name}"{desc_line}
Communities: {communities_str}{descriptions_block}{topics_block}

---

TASK: Generate search keywords that would help a user explore and discover relevant content within this audience's communities.

Generate 15-25 keywords/phrases that:
1. Reflect real pain points, questions, and interests of the community members
2. Are specific enough to return relevant results when searched in these communities
3. Cover different aspects: problems, desires, recommendations, trends, and common questions
4. Are in the natural language that community members would use

For each keyword, classify its category:
- pain_point: Problems, frustrations, or challenges people face
- question: Common questions people ask
- recommendation: Products, tools, or solutions people seek
- trend: Emerging topics or growing discussions
- general: General interest topics

And assign a relevance score (1-10) based on how likely this keyword will surface valuable discussions.

Respond in this exact format, one keyword per line:
KEYWORD|CATEGORY|RELEVANCE_SCORE

Examples:
best tools for|recommendation|9
struggling with|pain_point|8
how do you|question|7
anyone tried|recommendation|8
what's the best|question|9
frustrated with|pain_point|7
new to|general|6
trending in|trend|7

IMPORTANT:
- Keywords should be contextual to the audience, not generic
- Include a mix of short phrases (2-3 words) and longer search queries (4-6 words)
- Focus on terms that reveal user intent (buying, learning, solving, comparing)
- Do NOT include any other text, headers, or numbering. Just the pipe-delimited lines."""

    return prompt + get_language_directive(language)
