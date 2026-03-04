import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.semantic_search.application.services.post_embedding_service import (
    PostEmbeddingService,
)
from app.modules.semantic_search.application.use_cases.semantic_search_use_case.agent.semantic_search_agent import (
    create_semantic_search_agent,
)
from app.modules.semantic_search.domain.entities.semantic_search_log import (
    SemanticSearchLog,
)
from app.modules.shared.application.services.llm_cache_service import (
    LLMCacheService,
    TaskType,
)
from app.modules.theme_analysis.infra.repositories.theme_analysis_repository import (
    ThemeAnalysisRepository,
)

logger = logging.getLogger(__name__)

MAX_SIMILAR_POSTS = 50
MIN_SIMILARITY = 0.3


class SemanticSearchUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.theme_repo = ThemeAnalysisRepository(db)
        self.embedding_service = PostEmbeddingService(db)
        self.cache_service = LLMCacheService(db)

    def execute(
        self,
        audience_id: UUID,
        user_id: UUID,
        query: str,
        language: str = "en",
        limit: int = MAX_SIMILAR_POSTS,
    ) -> dict:
        audience = self.audience_repo.find_by_id(audience_id)
        if not audience:
            return {"error": "Audience not found"}

        communities = self.audience_repo.get_communities(audience_id)
        community_names = [c.subreddit_name for c in communities]

        # Check cache
        normalized_query = query.strip().lower()
        cache_key = f"semantic:{audience_id}:{normalized_query}"
        cached_result = self.cache_service.get(cache_key, TaskType.SEMANTIC_SEARCH)
        if cached_result:
            logger.info("Semantic search: cache hit for query '%s'", query[:50])
            self._safe_create_log(
                audience_id=audience_id,
                user_id=user_id,
                query=query,
                answer=cached_result.get("answer"),
                total_posts_searched=cached_result.get("total_posts_searched", 0),
                total_posts_matched=cached_result.get("total_posts_matched", 0),
                pattern_count=cached_result.get("pattern_count", 0),
                context_quality=cached_result.get("context_quality", "limited"),
                cached=True,
            )
            return {**cached_result, "cached": True}

        # 1. Collect ALL posts for this audience (across all theme_analyses)
        all_posts = self._collect_audience_posts(audience_id)
        if not all_posts:
            return {
                "answer": "No posts found for this audience. Run a theme analysis first.",
                "patterns": [],
                "total_posts_searched": 0,
                "total_posts_matched": 0,
                "pattern_count": 0,
                "context_quality": "limited",
                "cached": False,
                "query": query,
            }

        # 2. Ensure all posts have embeddings
        self.embedding_service.ensure_posts_embedded(all_posts)

        # 3. Embed the query
        query_embedding = self.embedding_service.embed_query(query)

        # 4. Find similar posts via pgvector
        post_reddit_ids = list({tp.post_reddit_id for tp in all_posts})
        similar = self.embedding_service.repository.find_similar_for_audience(
            query_embedding=query_embedding,
            post_reddit_ids=post_reddit_ids,
            limit=limit,
            min_similarity=MIN_SIMILARITY,
        )

        # 5. Enrich matched posts with full data from ThemePost
        posts_map: dict = {}
        for tp in all_posts:
            if tp.post_reddit_id not in posts_map:
                posts_map[tp.post_reddit_id] = tp

        matched_posts = []
        for item in similar:
            tp = posts_map.get(item["post_reddit_id"])
            if tp:
                matched_posts.append(
                    {
                        "post_reddit_id": tp.post_reddit_id,
                        "subreddit": tp.subreddit,
                        "title": tp.title,
                        "selftext": tp.selftext,
                        "score": tp.score or 0,
                        "num_comments": tp.num_comments or 0,
                        "permalink": tp.permalink or "",
                        "similarity": item["similarity"],
                    }
                )

        # 6. Run LangGraph agent
        agent = create_semantic_search_agent()
        result = agent.invoke(
            {
                "audience_name": audience.name,
                "community_names": community_names,
                "language": language,
                "query": query,
                "matched_posts": matched_posts,
                "total_audience_posts": len(post_reddit_ids),
                "context_quality": "limited",
                "answer": None,
                "patterns": None,
            }
        )

        answer = result.get("answer")
        patterns = result.get("patterns", [])
        context_quality = result.get("context_quality", "limited")

        response = {
            "answer": answer,
            "patterns": patterns,
            "total_posts_searched": len(post_reddit_ids),
            "total_posts_matched": len(matched_posts),
            "pattern_count": len(patterns),
            "context_quality": context_quality,
            "cached": False,
            "query": query,
        }

        # Persist log
        self._safe_create_log(
            audience_id=audience_id,
            user_id=user_id,
            query=query,
            answer=answer,
            total_posts_searched=len(post_reddit_ids),
            total_posts_matched=len(matched_posts),
            pattern_count=len(patterns),
            context_quality=context_quality,
            cached=False,
        )

        # Cache result
        self.cache_service.set(cache_key, TaskType.SEMANTIC_SEARCH, response)

        logger.info(
            "Semantic search: '%s' -> %d/%d posts matched, %d patterns (quality: %s)",
            query[:50],
            len(matched_posts),
            len(post_reddit_ids),
            len(patterns),
            context_quality,
        )

        return response

    def _collect_audience_posts(self, audience_id: UUID) -> list:
        """
        Collect ALL theme_posts across ALL theme_analyses for this audience.
        Returns deduplicated list (by post_reddit_id, keeping the first occurrence).
        """
        analyses_week = self.theme_repo.find_latest_by_audience_and_window(
            audience_id, "week"
        )
        analyses_month = self.theme_repo.find_latest_by_audience_and_window(
            audience_id, "month"
        )

        all_posts = []
        for analysis in [analyses_week, analyses_month]:
            if analysis and analysis.status == "ready":
                posts = self.theme_repo.get_posts(analysis.id)
                all_posts.extend(posts)

        seen: set[str] = set()
        unique_posts = []
        for p in all_posts:
            if p.post_reddit_id not in seen:
                seen.add(p.post_reddit_id)
                unique_posts.append(p)

        return unique_posts

    def _safe_create_log(self, **kwargs) -> None:
        try:
            log = SemanticSearchLog(**kwargs)
            self.db.add(log)
            self.db.commit()
        except Exception:
            logger.exception("Failed to create semantic search log")
            self.db.rollback()
