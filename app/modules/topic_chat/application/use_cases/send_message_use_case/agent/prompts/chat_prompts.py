from app.modules.shared.application.helpers.language_directive import (
    get_language_directive,
)


def topic_chat_system_prompt(
    topic_name: str,
    topic_description: str,
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
            "\n\nNOTE: You only have basic topic metadata (no analysis data available). "
            "Be transparent about this limitation. Answer what you can based on the topic name, "
            "description, and community context, but clearly state when you don't have enough "
            "data to give a detailed answer. Suggest the user run analyses (Deep Dive, Sentiment, Patterns) for richer results."
        )
    elif context_quality == "partial":
        quality_note = (
            "\n\nNOTE: You have partial analysis data. Some analyses (deep dive, sentiment, or patterns) "
            "are not yet available. Answer based on what you have, but note when additional analyses "
            "could provide deeper insights."
        )

    prompt = f"""You are an expert analyst specialized in online community research.
You are having a conversation with a user about a specific topic.

Audience: "{audience_name}"
Communities: {communities_str}
Topic: "{topic_name}"
Topic description: {topic_description}

CONTEXT DATA:
{context_text}
{quality_note}

INSTRUCTIONS:
- Answer EXCLUSIVELY based on the context data provided above
- Cite concrete data: tools mentioned, sentiments, patterns, specific examples from posts
- If the information is not in the context, explicitly say there is not enough data
- Be direct and actionable
- Use a maximum of 4 paragraphs per response
- Do NOT invent data or make assumptions beyond what the context shows
- Consider the conversation history to provide coherent follow-up answers
- If the user refers to something from a previous message, use that context naturally"""

    return prompt + get_language_directive(language)
