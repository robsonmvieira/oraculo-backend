"""Prompts para o agente de Product Intelligence."""

from app.modules.shared.application.helpers.language_directive import (
    get_language_directive,
)


def extract_products_prompt(
    audience_name: str,
    community_names: list[str],
    posts_text: str,
    enrichment_context: str,
    total_posts: int,
    language: str = "en",
) -> str:
    """Prompt para extrair todas as menções de produtos/marcas dos posts."""
    communities_str = ", ".join(f"r/{name}" for name in community_names)

    prompt = f"""You are an expert product/market analyst specializing in extracting product and brand mentions from Reddit discussions.

Audience: "{audience_name}"
Communities: {communities_str}
Total posts analyzed: {total_posts}

Below are Reddit posts from this audience:

{posts_text}

---

{enrichment_context}

---

TASK: Extract ALL product, brand, tool, service, SaaS, and platform mentions from the posts above.

For each unique product found, provide:

1. **product_name**: The canonical/official name of the product (properly capitalized)
2. **normalized_name**: Lowercase version for deduplication (e.g., "mailchimp")
3. **category**: One of: "tool", "service", "brand", "platform", "saas", "physical_product"
4. **total_mentions**: How many times this product appears across all posts (count accurately)
5. **sentiment_score**: A float from -1.0 (very negative) to 1.0 (very positive). 0.0 is neutral.
6. **sentiment_label**: "positive" (score > 0.25), "negative" (score < -0.25), "neutral" (score between -0.25 and 0.25), or "mixed" (conflicting opinions)
7. **trend_direction**: "rising" (gaining popularity), "stable", or "declining" (losing favor). Infer from context.
8. **positive_aspects**: Array of specific things people praise about this product (max 5)
9. **negative_aspects**: Array of specific complaints or limitations (max 5)
10. **gaps**: Array of features/capabilities users wish this product had (max 5)
11. **alternatives**: Array of objects with competing products mentioned in the same context: [{{"name": "...", "sentiment_label": "..."}}]
12. **evidence_quotes**: Array of direct quotes or close paraphrases from posts (max 5): [{{"quote": "...", "source_subreddit": "...", "score": N}}]
13. **communities**: Array of subreddit names where this product is mentioned
14. **use_cases**: Array of specific ways people use this product (max 5)

IMPORTANT RULES:
- Extract ONLY products/brands/tools/services explicitly mentioned in the posts. Do NOT invent products.
- If a product is mentioned by different names or abbreviations, consolidate into ONE entry with the most common name.
- If the ENRICHMENT DATA section contains products already extracted by other analyses, cross-reference with your findings to improve accuracy and add any missing details.
- Every claim MUST be backed by actual post content. Do NOT fabricate evidence.
- If there aren't enough posts to assess sentiment or trend, use null for those fields.
- Be thorough — scan titles AND body text of every post.
- Minimum threshold: only include products with at least 1 clear mention.
- Sort by total_mentions descending.

Respond ONLY with a valid JSON array of product objects. No markdown code blocks, no explanations outside the JSON.

Example: [{{"product_name": "Notion", "normalized_name": "notion", "category": "saas", "total_mentions": 12, ...}}]"""

    return prompt + get_language_directive(language)


def detect_opportunities_prompt(
    audience_name: str,
    community_names: list[str],
    product_profiles_text: str,
    solution_requests_text: str,
    total_products: int,
    language: str = "en",
) -> str:
    """Prompt para detectar oportunidades de mercado."""
    communities_str = ", ".join(f"r/{name}" for name in community_names)

    prompt = f"""You are a market opportunity analyst specializing in identifying gaps and opportunities from community discussions.

Audience: "{audience_name}"
Communities: {communities_str}
Total products analyzed: {total_products}

PRODUCT PROFILES (extracted from community discussions):

{product_profiles_text}

---

SOLUTION REQUESTS (posts where people are actively looking for products/solutions):

{solution_requests_text}

---

TASK: Analyze the product profiles and solution requests to identify market opportunities. Look for:

1. **unmet_demand**: People are asking for solutions that don't exist or have very few options. High demand + low supply.
2. **declining_product**: Products losing favor (negative sentiment, people switching away). Opportunity to offer better alternative.
3. **underserved_niche**: Specific use cases or communities with many discussions but few product solutions.
4. **emerging_trend**: New product categories or use cases gaining traction that are still early-stage.

For each opportunity, provide:

- **opportunity_type**: One of "unmet_demand", "declining_product", "underserved_niche", "emerging_trend"
- **title**: Short, clear title describing the opportunity (max 100 chars)
- **description**: 2-3 sentences explaining why this is an opportunity, with specific data points
- **opportunity_score**: Float 0-100 based on:
  - demand_signals strength (how many people want this)
  - pain intensity (how frustrated are they)
  - existing solutions quality (how well-served are they currently)
  Formula: high demand + high pain + low existing quality = high score
- **demand_signals**: Count of posts/mentions indicating demand
- **existing_solutions_count**: How many current products partially address this need
- **evidence**: Array of supporting quotes: [{{"quote": "...", "subreddit": "...", "post_url": ""}}]
- **related_products**: Array of product names related to this opportunity

IMPORTANT RULES:
- Base ALL opportunities on actual data from the profiles and solution requests. Do NOT speculate.
- Be specific — "people want a better X for Y use case" is better than "there's demand for better tools".
- Prioritize opportunities with the strongest evidence (multiple posts, high engagement).
- Return 3-10 opportunities, sorted by opportunity_score descending.
- If there isn't enough data to identify opportunities, return fewer items (or empty array).
- Do NOT fabricate evidence or inflate scores.

Respond ONLY with a valid JSON array of opportunity objects. No markdown code blocks, no explanations outside the JSON.

Example: [{{"opportunity_type": "unmet_demand", "title": "No affordable CRM for solopreneurs", "description": "...", "opportunity_score": 85, ...}}]"""

    return prompt + get_language_directive(language)
