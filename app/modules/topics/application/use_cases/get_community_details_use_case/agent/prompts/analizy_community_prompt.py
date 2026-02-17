def analyze_community_node_prompt(title: str, public_description: str) -> str:
    """
    Prompt para analisar a comunidade
    """

    return f"""You are an expert in Reddit communities.

Analyze this community:
- Title: {title}
- Description: {public_description}

Generate exactly 10 search terms in English that would find related communities on Reddit.
The terms should be specific and different from the original title.

Respond ONLY with the 10 terms separated by comma, without explanations.
Example: programming, software, coding, developer, tech, computer science, algorithms, web development, backend, frontend"""
