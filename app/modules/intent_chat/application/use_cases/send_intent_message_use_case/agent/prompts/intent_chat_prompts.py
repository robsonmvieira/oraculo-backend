from app.modules.shared.application.helpers.language_directive import (
    get_language_directive,
)


def intent_chat_system_prompt(
    intent_category: str,
    audience_name: str,
    community_names: list[str],
    context_text: str,
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

    category_focus = {
        "pain_and_anger": {
            "specialization": "understanding user frustrations, complaints, and emotional pain points",
            "focus": "pain points, frustrations, anger patterns, and emotional signals",
            "data_types": "emotions identified, behavioral patterns, specific examples from posts",
            "goal": "help the user understand what causes pain in this audience",
        },
        "solution_request": {
            "specialization": "understanding what solutions, tools, and resources people are actively seeking",
            "focus": "solution types being sought, tools requested, automation needs, and recurring solution patterns",
            "data_types": "solution types identified, seeking patterns, specific examples from posts",
            "goal": "help the user understand what solutions this audience is looking for",
        },
    }
    focus = category_focus.get(intent_category, category_focus["pain_and_anger"])

    prompt = f"""You are an expert analyst specialized in online community research,
specifically in {focus['specialization']}.
You are having a conversation with a user about the {category_label} intent category.

Audience: "{audience_name}"
Communities: {communities_str}
Intent Category: {category_label}

CONTEXT DATA:
{context_text}
{quality_note}

INSTRUCTIONS:
- Answer EXCLUSIVELY based on the context data provided above
- Focus on {focus['focus']}
- Cite concrete data: {focus['data_types']}
- If the information is not in the context, explicitly say there is not enough data
- Be direct and actionable — {focus['goal']}
- Use a maximum of 4 paragraphs per response
- Do NOT invent data or make assumptions beyond what the context shows
- Consider the conversation history to provide coherent follow-up answers
- If the user refers to something from a previous message, use that context naturally"""

    return prompt + get_language_directive(language)
