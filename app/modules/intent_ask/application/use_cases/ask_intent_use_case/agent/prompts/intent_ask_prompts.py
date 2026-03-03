from app.modules.shared.application.helpers.language_directive import (
    get_language_directive,
)


def intent_ask_prompt(
    intent_category: str,
    audience_name: str,
    community_names: list[str],
    context_text: str,
    question: str,
    context_quality: str,
    language: str = "en",
) -> str:
    communities_str = ", ".join(f"r/{name}" for name in community_names)

    quality_note = ""
    if context_quality == "limited":
        quality_note = (
            "\n\nNOTE: You only have basic intent metadata (no detailed analysis available). "
            "Be transparent about this limitation. Answer what you can based on the intent category "
            "and community context, but clearly state when you don't have enough "
            "data to give a detailed answer. Suggest the user run the Intent Classification analysis for richer results."
        )

    category_labels = {
        "pain_and_anger": "Pain & Anger",
        "advice_request": "Advice Requests",
        "solution_request": "Solution Requests",
        "self_promotion": "Self-Promotion",
        "ideas": "Ideas",
        "news": "News",
    }
    category_label = category_labels.get(intent_category, intent_category)

    prompt = f"""You are an expert analyst specialized in online community research,
specifically in understanding user frustrations, complaints, and emotional pain points.

Audience: "{audience_name}"
Communities: {communities_str}
Intent Category: {category_label}

CONTEXT DATA:
{context_text}

---

USER QUESTION:
"{question}"
{quality_note}

INSTRUCTIONS:
- Answer EXCLUSIVELY based on the context data provided above
- Focus on pain points, frustrations, anger patterns, and emotional signals
- Cite concrete data: emotions identified, behavioral patterns, specific examples from posts
- If the information is not in the context, explicitly say there is not enough data
- Be direct and actionable — help the user understand what causes pain in this audience
- Use a maximum of 4 paragraphs
- Do NOT invent data or make assumptions beyond what the context shows"""

    return prompt + get_language_directive(language)
