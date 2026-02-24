from app.modules.shared.application.helpers.language_directive import (
    get_language_directive,
)


def topic_qa_prompt(
    topic_name: str,
    topic_description: str,
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
            "\n\nNOTE: You only have basic topic metadata (no deep dive analysis available). "
            "Be transparent about this limitation. Answer what you can based on the topic name, "
            "description, and community context, but clearly state when you don't have enough "
            "data to give a detailed answer. Suggest the user run a Deep Dive analysis for richer results."
        )

    prompt = f"""You are an expert analyst specialized in online community research.

Audience: "{audience_name}"
Communities: {communities_str}
Topic: "{topic_name}"
Topic description: {topic_description}

CONTEXT DATA:
{context_text}

---

USER QUESTION:
"{question}"
{quality_note}

INSTRUCTIONS:
- Answer EXCLUSIVELY based on the context data provided above
- Cite concrete data: tools mentioned, sentiments, patterns, specific examples from posts
- If the information is not in the context, explicitly say there is not enough data
- Be direct and actionable
- Use a maximum of 4 paragraphs
- Do NOT invent data or make assumptions beyond what the context shows"""

    return prompt + get_language_directive(language)
