"""Use case that orchestrates audience expansion using the LangGraph agent."""

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.application.use_cases.expand_audience_use_case.agent.audience_expansion_agent import (
    create_audience_expansion_agent,
)
from app.modules.audiences.application.use_cases.expand_audience_use_case.agent.state import (
    CandidateCommunity,
    CommunityInfo,
    RankedSuggestion,
)
from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.shared.infra.repositories.community_stats_repository import (
    CommunityStatsRepository,
)
from app.modules.shared.infra.repositories.related_subs_repository import (
    RelatedSubsRepository,
)
from app.modules.similar_communities.application.services.similar_communities_service import (
    SimilarCommunitiesService,
)
from app.modules.shared.application.services.llm_cache_service import (
    LLMCacheService,
    TaskType,
)
from app.modules.similar_communities.infra.repositories.user_feedback_repository import (
    UserFeedbackRepository,
)

logger = logging.getLogger(__name__)


@dataclass
class AudienceExpansionResult:
    audience_id: str
    audience_name: str
    audience_theme: str
    suggestions: list[dict]
    total_found: int
    filtered_by_feedback: int


class ExpandAudienceUseCase:
    """Orchestrates candidate collection from multiple sources and runs the LangGraph agent."""

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.stats_repo = CommunityStatsRepository(db)
        self.related_subs_repo = RelatedSubsRepository(db)
        self.similar_service = SimilarCommunitiesService(db)
        self.feedback_repo = UserFeedbackRepository(db)
        self.cache_service = LLMCacheService(db)

    def execute(
        self,
        audience_id: UUID,
        user_id: str,
        limit: int = 10,
    ) -> AudienceExpansionResult:
        audience = self.audience_repo.find_by_id(audience_id)
        if not audience:
            return AudienceExpansionResult(
                audience_id=str(audience_id),
                audience_name="",
                audience_theme="",
                suggestions=[],
                total_found=0,
                filtered_by_feedback=0,
            )

        # 1. Gather current audience communities with their stats
        audience_communities = self.audience_repo.get_communities(audience_id)
        community_names = [c.subreddit_name for c in audience_communities]

        if not community_names:
            return AudienceExpansionResult(
                audience_id=str(audience_id),
                audience_name=audience.name,
                audience_theme="",
                suggestions=[],
                total_found=0,
                filtered_by_feedback=0,
            )

        # Cache key: sorted community names + user_id (feedback is per-user)
        cache_key = f"{user_id}:{','.join(sorted(community_names))}:{limit}"

        cached = self.cache_service.get(cache_key, TaskType.AUDIENCE_EXPANSION)
        if cached:
            logger.info("Audience expansion cache HIT for %s", audience.name)
            # Re-filter cached suggestions against current feedback
            # (feedback may have changed after the cache was created)
            negative_names = self.feedback_repo.get_negative_feedback_names(user_id)
            negative_set = {n.lower() for n in negative_names}
            filtered_suggestions = [
                s for s in cached["suggestions"]
                if s.get("subreddit_name", s.get("name", "")).lower() not in negative_set
            ]
            return AudienceExpansionResult(
                audience_id=cached["audience_id"],
                audience_name=cached["audience_name"],
                audience_theme=cached["audience_theme"],
                suggestions=filtered_suggestions,
                total_found=len(filtered_suggestions),
                filtered_by_feedback=len(negative_names),
            )

        logger.info("Audience expansion cache MISS for %s — running agent", audience.name)

        # Build community info from stats
        stats_entities = self.stats_repo.find_by_names(community_names)
        stats_map = {s.subreddit_name: s for s in stats_entities}

        current_communities: list[CommunityInfo] = [
            CommunityInfo(
                name=name,
                title=stats_map[name].title if name in stats_map else None,
                description=stats_map[name].description if name in stats_map else None,
                subscribers=stats_map[name].subscribers if name in stats_map else None,
            )
            for name in community_names
        ]

        # 2. Build excluded names: audience communities + negative feedback
        excluded_names = [n.lower() for n in community_names]
        negative_names = self.feedback_repo.get_negative_feedback_names(user_id)
        excluded_names.extend(negative_names)
        filtered_by_feedback = len(negative_names)

        # 3. Collect candidates from external sources (before agent runs)
        candidates = self._collect_candidates(community_names, excluded_names, limit)

        # 4. Run the LangGraph agent
        agent = create_audience_expansion_agent()
        result = agent.invoke({
            "audience_id": str(audience_id),
            "audience_name": audience.name,
            "audience_description": audience.description,
            "current_communities": current_communities,
            "excluded_names": excluded_names,
            "user_id": user_id,
            "limit": limit,
            "audience_theme": "",
            "candidates": candidates,
            "suggestions": [],
        })

        # 5. Enrich suggestions with stats (size_tag, activity_tag, growth_week)
        suggestions = self._enrich_suggestions(result["suggestions"])

        expansion_result = AudienceExpansionResult(
            audience_id=str(audience_id),
            audience_name=audience.name,
            audience_theme=result.get("audience_theme", ""),
            suggestions=suggestions,
            total_found=len(suggestions),
            filtered_by_feedback=filtered_by_feedback,
        )

        # 6. Cache the result
        self.cache_service.set(cache_key, TaskType.AUDIENCE_EXPANSION, {
            "audience_id": expansion_result.audience_id,
            "audience_name": expansion_result.audience_name,
            "audience_theme": expansion_result.audience_theme,
            "suggestions": expansion_result.suggestions,
            "total_found": expansion_result.total_found,
            "filtered_by_feedback": expansion_result.filtered_by_feedback,
        })

        return expansion_result

    def _collect_candidates(
        self,
        community_names: list[str],
        excluded_names: list[str],
        limit: int,
    ) -> list[CandidateCommunity]:
        """Collect candidate communities from embeddings and related_subs."""
        candidates: list[CandidateCommunity] = []
        seen = {n.lower() for n in excluded_names}

        # Source 1: Embedding similarity
        try:
            similar_result = self.similar_service.find_similar_to_audience(
                community_names=community_names,
                limit=limit * 2,
                min_similarity=0.4,
            )
            for s in similar_result.suggestions:
                if s.name.lower() not in seen:
                    seen.add(s.name.lower())
                    candidates.append(CandidateCommunity(
                        name=s.name,
                        title=s.title,
                        description=s.description,
                        subscribers=s.subscribers,
                        source="embedding",
                    ))
        except Exception:
            logger.exception("Error fetching embedding candidates")

        # Source 2: Related subs cache (from old.reddit scraping)
        try:
            for community_name in community_names:
                related = self.related_subs_repo.find_by_source(community_name)
                for rel in related:
                    if rel.related_sub.lower() not in seen:
                        seen.add(rel.related_sub.lower())
                        candidates.append(CandidateCommunity(
                            name=rel.related_sub,
                            title=rel.related_sub_title,
                            description=rel.related_sub_description,
                            subscribers=rel.related_sub_subscribers,
                            source="related_subs",
                        ))
        except Exception:
            logger.exception("Error fetching related_subs candidates")

        # Source 3: Community stats search by name patterns
        try:
            for community_name in community_names:
                stats_results, _ = self.stats_repo.browse(
                    search=community_name,
                    limit=5,
                )
                for stats in stats_results:
                    if stats.subreddit_name.lower() not in seen:
                        seen.add(stats.subreddit_name.lower())
                        candidates.append(CandidateCommunity(
                            name=stats.subreddit_name,
                            title=stats.title,
                            description=stats.description,
                            subscribers=stats.subscribers,
                            source="term_search",
                        ))
        except Exception:
            logger.exception("Error fetching stats candidates")

        logger.info("Collected %d candidates from all sources", len(candidates))
        return candidates

    def _enrich_suggestions(
        self, suggestions: list[RankedSuggestion]
    ) -> list[dict]:
        """Enrich suggestions with community_stats data (tags and growth)."""
        if not suggestions:
            return []

        names = [s["name"] for s in suggestions]
        stats_entities = self.stats_repo.find_by_names(names)
        stats_map = {s.subreddit_name: s for s in stats_entities}

        enriched = []
        for s in suggestions:
            stats = stats_map.get(s["name"].lower())
            enriched.append({
                "subreddit_name": s["name"],
                "title": s.get("title"),
                "description": s.get("description"),
                "subscribers": stats.subscribers if stats else s.get("subscribers"),
                "size_tag": stats.size_tag if stats else None,
                "activity_tag": stats.activity_tag if stats else None,
                "growth_week": stats.growth_week if stats else None,
                "relevance_score": round(s["relevance_score"], 4),
                "relevance_reason": s["relevance_reason"],
            })

        return enriched
