"""Browse communities with hybrid search: local DB + Reddit API fallback."""

import logging

from sqlalchemy.orm import Session

from app.modules.shared.infra.cache.redit_cache import RedisCache
from app.modules.shared.infra.repositories.community_stats_repository import (
    CommunityStatsRepository,
)
from app.modules.topics.infra.providers.reddit_provider.generic_reddit_provider import (
    GenericRedditProvider,
)

logger = logging.getLogger("oracle")

MIN_SUBSCRIBERS = 1000


class BrowseCommunitiesUseCase:

    def __init__(
        self,
        reddit_provider: GenericRedditProvider,
        cache: RedisCache,
        db: Session,
    ):
        self.reddit_provider = reddit_provider
        self.cache = cache
        self.repo = CommunityStatsRepository(db)

    def execute(
        self,
        sort: str = "subscribers",
        category: str | None = None,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        if not search:
            return self._browse_catalog(sort, category, limit, offset)

        return self._browse_with_search(sort, category, search, limit, offset)

    def _browse_catalog(
        self, sort: str, category: str | None, limit: int, offset: int
    ) -> dict:
        results, total = self.repo.browse(
            sort=sort, category=category, limit=limit, offset=offset,
        )
        logger.info(
            "[BROWSE] catalog mode | results=%d | total=%d", len(results), total,
        )
        return self._format_response(results, total, limit, offset)

    def _browse_with_search(
        self,
        sort: str,
        category: str | None,
        search: str,
        limit: int,
        offset: int,
    ) -> dict:
        # Fetch ALL local matches (no pagination at DB level)
        local_results, _ = self.repo.browse(
            sort=sort, category=category, search=search,
            limit=500, offset=0,
        )
        logger.info(
            "[BROWSE] search='%s' | local_matches=%d | limit=%d | offset=%d",
            search, len(local_results), limit, offset,
        )

        needs_fallback = len(local_results) < limit

        if not needs_fallback:
            all_results = self._sort_results(local_results, sort, search)
            page = all_results[offset:offset + limit]
            total = len(all_results)
            logger.info("[BROWSE] local sufficient, returning %d of %d", len(page), total)
            return self._format_response(page, total, limit, offset)

        # Fallback to Reddit (Redis cache serves page 2+ without hitting API)
        reddit_communities = self._fetch_reddit_communities(search)
        logger.info("[BROWSE] reddit fetched: %d", len(reddit_communities))

        filtered = self._filter_reddit_results(reddit_communities)
        logger.info(
            "[BROWSE] after filter (>=%d subs, not NSFW): %d passed",
            MIN_SUBSCRIBERS, len(filtered),
        )

        local_names = {c.subreddit_name.lower() for c in local_results}
        new_communities = [
            c for c in filtered
            if c["display_name"].lower() not in local_names
        ]
        logger.info("[BROWSE] dedup: %d new, %d already local",
            len(new_communities), len(filtered) - len(new_communities),
        )

        saved_entities = self._persist_reddit_results(new_communities)
        logger.info("[BROWSE] persisted: %d", len(saved_entities))

        all_results = list(local_results) + saved_entities
        all_results = self._sort_results(all_results, sort, search)
        total = len(all_results)
        page = all_results[offset:offset + limit]

        final_names = [c.subreddit_name for c in page]
        logger.info("[BROWSE] final: %d of %d | %s", len(page), total, final_names)

        return self._format_response(page, total, limit, offset)

    def _fetch_reddit_communities(self, search: str) -> list[dict]:
        cache_key = f"browse_reddit_search_{search.lower()}"

        try:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        except Exception:
            logger.warning("Redis cache read failed for key='%s'", cache_key)

        try:
            reddit_data = self.reddit_provider.search_community_by_name(
                search, limit=30
            )
            children = reddit_data.get("data", {}).get("children", [])
            communities = [child["data"] for child in children if "data" in child]

            try:
                self.cache.set(cache_key, communities, ttl=1800)
            except Exception:
                logger.warning("Redis cache write failed for key='%s'", cache_key)

            return communities
        except Exception:
            logger.warning(
                "Reddit API fallback failed for search='%s'",
                search,
                exc_info=True,
            )
            return []

    def _filter_reddit_results(self, communities: list[dict]) -> list[dict]:
        return [
            c for c in communities
            if (c.get("subscribers") or 0) >= MIN_SUBSCRIBERS
            and not c.get("over18", False)
        ]

    def _persist_reddit_results(self, communities: list[dict]) -> list:
        saved = []
        for c in communities:
            name = c.get("display_name", "")
            if not name:
                continue

            icon_url = c.get("community_icon") or c.get("icon_img") or None
            if icon_url:
                icon_url = icon_url.replace("&amp;", "&")

            try:
                entity = self.repo.upsert(
                    subreddit_name=name,
                    title=c.get("title"),
                    description=c.get("public_description"),
                    subscribers=c.get("subscribers"),
                    icon_url=icon_url,
                )
                saved.append(entity)
            except Exception:
                logger.warning(
                    "Failed to persist Reddit community '%s'",
                    name,
                    exc_info=True,
                )
                continue
        return saved

    @staticmethod
    def _sort_results(
        results: list, sort: str, search: str | None = None
    ) -> list:
        sort_key_map = {
            "subscribers": lambda c: c.subscribers or 0,
            "growth_week": lambda c: c.growth_week or 0,
            "growth_month": lambda c: c.growth_month or 0,
        }
        metric_fn = sort_key_map.get(sort, sort_key_map["subscribers"])

        if not search:
            return sorted(results, key=metric_fn, reverse=True)

        term = search.lower()

        def relevance_key(c):
            name = c.subreddit_name.lower()
            # Tier 0: exact match (highest priority)
            # Tier 1: name contains search term
            # Tier 2: everything else
            if name == term:
                tier = 0
            elif term in name:
                tier = 1
            else:
                tier = 2
            return (tier, -(metric_fn(c)))

        return sorted(results, key=relevance_key)

    @staticmethod
    def _format_response(
        results: list, total: int, limit: int, offset: int
    ) -> dict:
        return {
            "communities": [
                {
                    "name": c.subreddit_name,
                    "title": c.title,
                    "description": c.description,
                    "subscribers": c.subscribers,
                    "icon_url": c.icon_url,
                    "growth_week": c.growth_week,
                    "growth_month": c.growth_month,
                    "category": c.category,
                }
                for c in results
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total,
        }
