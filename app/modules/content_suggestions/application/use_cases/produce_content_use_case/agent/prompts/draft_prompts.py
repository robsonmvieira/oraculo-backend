"""Prompts para geracao de conteudo completo por plataforma (Node 1)."""


PLATFORM_RULES = {
    "linkedin": {
        "name": "LinkedIn",
        "max_chars": 3000,
        "tone": "professional yet conversational",
        "rules": [
            "Use line breaks every 2-3 sentences for readability",
            "Start with a strong hook (first line visible in feed)",
            "Include data points and evidence to build credibility",
            "End with a clear CTA (question, comment prompt, or link)",
            "Use 3-5 relevant hashtags at the end",
            "Avoid overly promotional language — focus on insight and value",
        ],
        "format_notes": "Single post or carousel (numbered slides with short text per slide)",
        "image_aspect_ratio": "16:9",
    },
    "twitter": {
        "name": "Twitter/X",
        "max_chars_per_tweet": 280,
        "max_tweets": 10,
        "tone": "conversational, punchy, direct",
        "rules": [
            "Thread format: number each tweet (1/, 2/, etc.)",
            "First tweet is the hook — must stand alone and be compelling",
            "Each tweet should be a complete thought",
            "Use short sentences and line breaks",
            "Last tweet: CTA + recap of the key insight",
            "2-3 relevant hashtags only on the last tweet",
            "No emojis overload — 1-2 per tweet max",
        ],
        "format_notes": "Thread of 5-10 tweets (280 chars each)",
        "image_aspect_ratio": "16:9",
    },
    "instagram": {
        "name": "Instagram",
        "max_chars_caption": 2200,
        "tone": "relatable, visual-first, storytelling",
        "rules": [
            "Caption: hook in first line (visible before 'more')",
            "If carousel: each slide has 1 key idea, max 6-8 words per line",
            "Use storytelling arc: hook → problem → insight → solution → CTA",
            "Include 10-15 relevant hashtags (mix of popular and niche)",
            "Add a CTA: 'Save this for later', 'Tag someone who needs this'",
            "Use line breaks and emojis sparingly for structure",
        ],
        "format_notes": "Carousel (10 slides max, short text per slide) + caption",
        "image_aspect_ratio": "1:1",
    },
    "reddit": {
        "name": "Reddit",
        "max_chars": 40000,
        "tone": "authentic, non-promotional, community-first",
        "rules": [
            "Title: specific and descriptive (not clickbait)",
            "Body: genuine, detailed, first-person perspective preferred",
            "NO marketing language or self-promotion",
            "Include data or personal experience to build trust",
            "Reference community norms and language",
            "End with a question to encourage discussion",
            "No hashtags — Reddit doesn't use them",
        ],
        "format_notes": "Post title + body text (markdown supported)",
        "image_aspect_ratio": "16:9",
    },
}


def get_draft_content_prompt(
    suggestion: dict,
    platforms: list[str],
    audience_name: str,
    communities_str: str,
    language_directive: str,
) -> str:
    """Prompt para o no de geracao de conteudo."""
    platform_specs = []
    for p in platforms:
        rules = PLATFORM_RULES.get(p, PLATFORM_RULES["linkedin"])
        rules_text = "\n".join(f"  - {r}" for r in rules["rules"])
        platform_specs.append(
            f"### {rules['name']}\n"
            f"- Format: {rules['format_notes']}\n"
            f"- Tone: {rules['tone']}\n"
            f"- Image aspect ratio: {rules.get('image_aspect_ratio', '16:9')}\n"
            f"- Rules:\n{rules_text}"
        )

    platforms_block = "\n\n".join(platform_specs)

    import json
    suggestion_json = json.dumps(suggestion, indent=2, ensure_ascii=False)

    return f"""You are an expert content creator and copywriter. Your job is to transform a content strategy suggestion into COMPLETE, READY-TO-PUBLISH content for specific social media platforms.

## AUDIENCE
- Name: {audience_name}
- Communities: {communities_str}

## CONTENT SUGGESTION (strategy brief)
{suggestion_json}

## TARGET PLATFORMS AND RULES
{platforms_block}

## YOUR TASK
For EACH target platform, create a complete content piece with:

1. **hooks**: Array of 3 hook options for the opening line. Each hook should:
   - Stop the scroll (pattern interrupt)
   - Use the audience's own language (from keywords and evidence)
   - Create curiosity, urgency, or emotional resonance
   - Format: [{{"option": 1, "text": "..."}}]

2. **full_draft**: The COMPLETE content text, ready to copy-paste and publish.
   - Follow the outline from the suggestion but EXPAND it into actual prose
   - Use the approach, emotional tone, and evidence from the suggestion
   - Respect the platform's character limits and formatting rules
   - Include the best hook as the opening (you'll provide alternatives in hooks)
   - For carousel/thread: clearly separate slides/tweets

3. **narrative_arc**: The storytelling structure used:
   - Problem/Hook: What pain point or question hooks the reader
   - Tension: What makes this urgent or emotionally charged
   - Resolution: The insight, answer, or call to action
   - Write 2-3 sentences describing the arc, not the content itself

4. **cta**: A specific call-to-action tailored to the platform and content format.

5. **platform_notes**: Brief notes about platform-specific adaptations made.

6. **hashtags**: Array of relevant hashtags (follow each platform's convention).

7. **image_aspect_ratio**: The recommended aspect ratio for the image on this platform.

## WRITING PRINCIPLES
1. **Real language**: Use terms, slang, and expressions the audience actually uses (from keywords and evidence)
2. **Evidence-backed**: Reference specific data, numbers, and real examples from the suggestion's evidence
3. **Counter-intuitive angles**: Don't just state the obvious — surprise, challenge, or reframe
4. **Platform-native**: Content must feel like it was written BY someone on that platform, not by a brand
5. **Emotional resonance**: Match the emotional_tone from the suggestion — make the reader FEEL something
6. **Actionable**: Every piece should leave the reader knowing what to do next

## FORMAT
Respond with a JSON array — one object per platform. No additional text.

```json
[
  {{
    "platform": "linkedin",
    "hooks": [{{"option": 1, "text": "..."}}],
    "full_draft": "...",
    "narrative_arc": "...",
    "cta": "...",
    "platform_notes": "...",
    "hashtags": ["#tag1", "#tag2"],
    "image_aspect_ratio": "16:9"
  }}
]
```{language_directive}"""
