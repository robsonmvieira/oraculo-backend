from app.modules.shared.application.helpers.language_directive import get_language_directive


def behavioral_pattern_detection_prompt(
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

    prompt = f"""You are an expert behavioral analyst specializing in detecting behavioral patterns from online community discussions.

Audience: "{audience_name}"
Communities: {communities_str}
Topic: "{topic_name}"
Topic description: {topic_description}
Total posts analyzed: {total_posts}
Total comments analyzed: {total_comments}

Below are posts and their top comments related to this topic:

{posts_with_comments_text}

---

TASK: Detect BEHAVIORAL PATTERNS within this topic. You are NOT summarizing what people talk about — you are identifying what people ARE DOING, what tools they use, what problems they face, and what they are actively looking for.

Produce a structured analysis in JSON format with the following sections:

1. **summary**: Write 2-3 paragraphs describing the behavioral landscape of this topic. Focus on ACTIONS people take, not opinions they hold. What are the dominant behaviors? What tools dominate? Where are the biggest frictions? What shifts are happening?

2. **tool_patterns**: Identify 3-8 tools, products, or services people use within this topic. For each:
   - "tool": Name of the tool/product/service
   - "use_case": What people use it for (be specific)
   - "satisfaction": "satisfied", "mixed", or "dissatisfied"
   - "pain_points": Array of specific complaints or limitations users mention (empty array if satisfied)
   - "evidence": A direct quote or paraphrased excerpt from posts/comments that supports this pattern
   - "communities": Array of subreddit names where this pattern appears

   Focus on tools people ACTUALLY mention using, not tools they wish existed.

3. **workaround_patterns**: Identify 2-6 workarounds or improvised solutions people have created when existing tools/approaches don't work. For each:
   - "problem": The specific problem they're trying to solve
   - "workaround": What they're doing instead (the hack, the manual process, the duct-tape solution)
   - "frequency": "common" (many people do this), "moderate" (some people), or "rare" (a few but notable)
   - "evidence": A direct quote or paraphrased excerpt
   - "communities": Array of subreddit names where this appears

   These are GOLD — they reveal unmet needs. Look for: manual processes, spreadsheet hacks, combining multiple tools, free alternatives to paid solutions, custom scripts, etc.

4. **friction_patterns**: Identify 3-8 recurring frictions, frustrations, or blockers people face. For each:
   - "friction": Clear description of the friction
   - "category": "pricing" (too expensive, bad pricing model), "complexity" (too hard to learn/use), "limitations" (missing features), "reliability" (bugs, downtime), "support" (bad customer service), or "integration" (doesn't work with other tools)
   - "severity": "high" (frequently mentioned, strong frustration), "medium" (mentioned occasionally), or "low" (minor annoyance)
   - "affected_tools": Array of tool/product names this friction relates to (empty array if general)
   - "evidence": A direct quote or paraphrased excerpt

5. **shift_patterns**: Identify 2-5 behavioral shifts or migrations happening. For each:
   - "from": What people are moving away from (tool, approach, mindset)
   - "to": What people are moving toward
   - "reason": Why the shift is happening
   - "stage": "early" (a few pioneers), "growing" (gaining momentum), or "established" (widely adopted)
   - "evidence": A direct quote or paraphrased excerpt

   Look for: tool migrations, methodology changes, attitude shifts, new approaches replacing old ones.

6. **demand_signals**: Identify 3-8 explicit signals of unmet demand. For each:
   - "signal": What people are asking for or looking for (be specific)
   - "signal_type": "tool_request" (looking for a tool), "how_to" (looking for a method/approach), "recommendation" (asking for suggestions), or "willingness_to_pay" (explicitly willing to pay for a solution)
   - "frequency": "high", "medium", or "low"
   - "communities": Array of subreddit names where this signal appears
   - "evidence": A direct quote or paraphrased excerpt

   Look for: "Does anyone know a tool that...", "How do you...", "I wish there was...", "I'd pay for...", "Looking for recommendations for...", "What do you use for..."

IMPORTANT:
- Focus on BEHAVIORS and ACTIONS, not opinions or sentiments.
- Every pattern MUST include real evidence from the posts/comments provided. Do NOT fabricate.
- If there isn't enough data for a section, provide fewer items rather than inventing patterns.
- Be specific — "people use Mailchimp for email automation" is better than "people use email tools".
- Quotes in "evidence" should be as close to the original text as possible.

Respond ONLY with valid JSON. No markdown code blocks, no explanations outside the JSON.

Example structure:
{{"summary": "...", "tool_patterns": [...], "workaround_patterns": [...], "friction_patterns": [...], "shift_patterns": [...], "demand_signals": [...]}}"""

    return prompt + get_language_directive(language)
