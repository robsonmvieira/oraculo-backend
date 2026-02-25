"""Prompts para o agente de geração de sumário narrativo."""


def get_generate_summary_prompt(
    audience_name: str,
    time_window: str,
    period_start: str,
    period_end: str,
    theme_name: str,
    communities_str: str,
    post_count: int,
    avg_score: float,
    avg_comments: float,
    top_subreddits_str: str,
    representative_posts_text: str,
    intent_section: str = "",
    week_diff_instruction: str = "",
    language_directive: str = "",
) -> str:
    """Prompt para geração de sumário narrativo enriquecido."""
    return f"""You are a community intelligence analyst writing a briefing for a product manager.

Audience: "{audience_name}"
Period: {time_window} ({period_start} to {period_end})
Theme: "{theme_name}"
Communities: {communities_str}

THEME METRICS:
- Total posts: {post_count}
- Average score: {avg_score:.1f}
- Average comments: {avg_comments:.1f}
- Top subreddits: {top_subreddits_str}

TOP POSTS:
{representative_posts_text}

{intent_section}

---

TASK: Write a rich narrative summary for this theme.

Your output should be a JSON object with these fields:

1. "narrative": A 2-4 paragraph summary in newsletter style. Write as if you're briefing someone
   who hasn't read any of the posts. Be specific — mention subreddit names, reference interesting
   posts by topic (not by title), capture the mood of the discussions. The narrative should feel
   like reading a "This week in {audience_name}" newsletter.

2. "highlights": An array of 3-5 notable posts that deserve attention. For each:
   {{"title": "...", "subreddit": "...", "score": N, "why_notable": "1-sentence reason"}}

3. "emotional_tone": One of: "positive", "mixed", "tense", "neutral", "celebratory", "concerned", "supportive"

4. "tone_description": A short phrase describing the overall emotional tone (e.g., "Warm and supportive with pockets of concern about vet costs")

5. "key_themes": Array of 3-7 sub-themes mentioned in the narrative:
   [{{"theme": "short name", "description": "1 sentence"}}]

{week_diff_instruction}

RULES:
- Return ONLY the JSON object, no additional text
- Do not wrap in markdown code fences
- The "highlights" should reference actual posts from the TOP POSTS section
- The "narrative" should be engaging and actionable, not generic

{language_directive}"""


def build_intent_section(intent_breakdown: dict) -> str:
    """Constrói a seção de intenções para o prompt, se dados disponíveis."""
    total = sum(intent_breakdown.values())
    if total == 0:
        return ""

    lines = ["INTENT BREAKDOWN (how people are engaging):"]
    intent_labels = {
        "advice_request": "Advice Requests",
        "pain_and_anger": "Pain & Anger",
        "solution_request": "Solution Requests",
        "self_promotion": "Self-Promotion",
        "ideas": "Ideas",
        "news": "News",
    }

    for key, label in intent_labels.items():
        count = intent_breakdown.get(key, 0)
        if count > 0:
            pct = (count / total) * 100
            lines.append(f"- {label}: {count} posts ({pct:.0f}%)")

    lines.append("")
    lines.append("Incorporate these intent patterns into the narrative naturally.")
    lines.append(
        "For example, if advice requests dominate, mention that the community is actively seeking guidance."
    )

    return "\n".join(lines)


def build_week_diff_instruction(time_window: str, previous_themes: list[str]) -> str:
    """Constrói instrução para diferenciador temporal, se dados históricos disponíveis."""
    previous_themes_str = ", ".join(previous_themes)
    return (
        f'6. "week_differentiator": One sentence explaining what made this {time_window} different from '
        f"the previous one. Last {time_window}'s themes were: {previous_themes_str}"
    )
