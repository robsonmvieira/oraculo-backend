from app.modules.shared.application.helpers.language_directive import get_language_directive


def analyze_audience_theme_prompt(communities: list[dict], language: str = "en") -> str:
    community_list = "\n".join(
        f"- r/{c['name']}: {c.get('title', 'N/A')} — {c.get('description', 'N/A')}"
        for c in communities
    )

    prompt = f"""You are an expert in Reddit communities and audience analysis.

Analyze this audience composed of the following communities:
{community_list}

Identify the central theme, niche, and target audience profile.
Then generate exactly 5 search terms that would help find NEW related communities on Reddit
that would be interesting for this audience.

Respond in this exact format (no extra text):
THEME: <one sentence describing the audience theme>
TERMS: <5 search terms separated by comma>"""

    return prompt + get_language_directive(language)


def rank_and_explain_prompt(
    audience_theme: str, candidates: list[dict], language: str = "en",
) -> str:
    candidate_list = "\n".join(
        f"- r/{c['name']} ({c.get('subscribers', 'N/A')} subscribers): "
        f"{c.get('title', 'N/A')} — {c.get('description', 'N/A')}"
        for c in candidates
    )

    prompt = f"""You are an expert in Reddit communities.

Audience theme: {audience_theme}

Rank these candidate communities by relevance to the audience theme.
For each one, provide a relevance score (0.0 to 1.0) and a brief reason (max 15 words) explaining why it's relevant.

Candidates:
{candidate_list}

Respond with one line per community in this exact format (no extra text):
r/<name>|<score>|<reason>

Order from most to least relevant. Only include communities with score >= 0.3."""

    return prompt + get_language_directive(language)
