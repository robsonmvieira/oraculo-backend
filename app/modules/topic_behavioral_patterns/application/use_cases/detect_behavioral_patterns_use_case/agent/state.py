from typing import TypedDict


class PostWithComments(TypedDict):
    id: str
    subreddit: str
    title: str
    selftext: str
    score: int
    num_comments: int
    created_utc: float
    permalink: str | None
    comments: list[dict]  # [{"body": "...", "score": N, "author": "..."}]


class BehavioralPatternResult(TypedDict):
    summary: str
    tool_patterns: list[dict]
    # [{"tool": "...", "use_case": "...", "satisfaction": "...", "evidence": "..."}]
    workaround_patterns: list[dict]
    # [{"problem": "...", "workaround": "...", "frequency": "...", "evidence": "..."}]
    friction_patterns: list[dict]
    # [{"friction": "...", "category": "...", "severity": "...", "evidence": "..."}]
    shift_patterns: list[dict]
    # [{"from": "...", "to": "...", "reason": "...", "evidence": "..."}]
    demand_signals: list[dict]
    # [{"signal": "...", "frequency": "...", "communities": [...], "evidence": "..."}]


class BehavioralPatternState(TypedDict):
    topic_name: str
    topic_description: str
    audience_name: str
    community_names: list[str]
    language: str

    # Populated by nodes
    relevant_posts: list[PostWithComments]
    pattern_result: BehavioralPatternResult | None
