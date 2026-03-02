"""Prompts para refinamento de drafts e hooks (Node 2)."""

import json


def get_refine_hooks_prompt(
    drafts_json: str,
    suggestion: dict,
    language_directive: str,
) -> str:
    """Prompt para o no de refinamento e validacao."""
    suggestion_summary = json.dumps(
        {
            "title": suggestion.get("title"),
            "approach": suggestion.get("approach"),
            "emotional_tone": suggestion.get("emotional_tone"),
            "keywords": suggestion.get("keywords"),
            "evidence": suggestion.get("evidence"),
        },
        indent=2,
        ensure_ascii=False,
    )

    return f"""You are a senior content editor and hook specialist. Your job is to review content drafts and ensure maximum impact before publishing.

## ORIGINAL STRATEGY
{suggestion_summary}

## DRAFTS TO REVIEW
{drafts_json}

## YOUR TASK
Review each platform draft and refine:

### 1. HOOK QUALITY
For each platform's hooks:
- Is the first hook genuinely scroll-stopping? Would YOU stop to read it?
- Does it create curiosity, tension, or emotional pull?
- Does it use the audience's vocabulary (not generic marketing speak)?
- If any hook is weak, rewrite it. All 3 options should be strong.

### 2. CROSS-PLATFORM CONSISTENCY
- All drafts should convey the SAME core message/insight
- But each should feel NATIVE to its platform (not just copy-pasted)
- Verify each draft respects the platform's tone and format rules

### 3. CTA EFFECTIVENESS
- Is the CTA specific and actionable?
- Does it match the platform's engagement patterns?
  - LinkedIn: "What's your experience with...?" / "Share your take below"
  - Twitter: "Retweet if you agree" / "What would you add?" (in last tweet)
  - Instagram: "Save this for later" / "Tag someone who needs to see this"
  - Reddit: Open question to spark discussion

### 4. CONTENT QUALITY
- Remove filler words and generic statements
- Ensure evidence/data is cited accurately
- Verify the emotional tone matches throughout
- Check character/format limits are respected

Return the complete refined drafts in the same JSON structure. If a draft is already strong, keep it as-is.

Respond with a JSON array only. No additional text.

```json
[
  {{
    "platform": "...",
    "hooks": [{{"option": 1, "text": "..."}}],
    "full_draft": "...",
    "narrative_arc": "...",
    "cta": "...",
    "platform_notes": "...",
    "hashtags": ["#tag1"],
    "image_aspect_ratio": "..."
  }}
]
```{language_directive}"""
