import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.intent_ask.application.use_cases.ask_intent_use_case.agent.intent_ask_agent import (
    create_intent_ask_agent,
)
from app.modules.intent_ask.infra.repositories.intent_ask_repository import (
    IntentAskRepository,
)
from app.modules.intent_classification.infra.repositories.intent_classification_repository import (
    IntentClassificationRepository,
)
from app.modules.shared.application.services.llm_cache_service import (
    LLMCacheService,
    TaskType,
)
from app.modules.theme_analysis.infra.repositories.theme_analysis_repository import (
    ThemeAnalysisRepository,
)
from app.modules.theme_analysis.infra.repositories.theme_summary_repository import (
    ThemeSummaryRepository,
)

logger = logging.getLogger(__name__)


class AskIntentUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.intent_repo = IntentClassificationRepository(db)
        self.theme_repo = ThemeAnalysisRepository(db)
        self.theme_summary_repo = ThemeSummaryRepository(db)
        self.ask_repo = IntentAskRepository(db)
        self.cache_service = LLMCacheService(db)

    def execute(
        self,
        audience_id: UUID,
        user_id: UUID,
        intent_category: str,
        question: str,
        window: str = "week",
        language: str = "en",
    ) -> dict:
        """
        Responde uma pergunta sobre uma categoria de intencao usando dados
        de intent classification e theme analysis como contexto.

        Returns:
            dict com answer, context_quality, sources_used, cached, intent_category, suggestion
        """
        audience = self.audience_repo.find_by_id(audience_id)
        if not audience:
            return {"error": "Audience not found"}

        communities = self.audience_repo.get_communities(audience_id)
        community_names = [c.subreddit_name for c in communities]

        # Check cache
        cache_key = f"intent:{audience_id}:{intent_category}:{window}:{question.strip().lower()}"
        cached_result = self.cache_service.get(cache_key, TaskType.INTENT_QA)
        if cached_result:
            logger.info("Intent Ask: cache hit for category '%s'", intent_category)
            self._safe_create_log(
                analysis_id=cached_result.get("analysis_id"),
                audience_id=audience_id,
                user_id=user_id,
                intent_category=intent_category,
                question=question,
                answer=cached_result.get("answer"),
                context_quality=cached_result.get("context_quality", "limited"),
                cached=True,
            )
            return {**cached_result, "cached": True}

        # Fetch intent classification data
        intent_context = None
        context_quality = "limited"
        sources_used = ["intent_metadata"]
        analysis_id = None

        intent_analysis = self.intent_repo.find_latest_by_audience_and_window(
            audience_id, window
        )
        pain_summary = None
        if intent_analysis and intent_analysis.status == "ready":
            analysis_id = intent_analysis.id
            summaries = self.intent_repo.get_intent_summaries(intent_analysis.id)
            pain_summary = next(
                (s for s in summaries if s.intent_category == intent_category),
                None,
            )

        # Fetch theme summaries for broader context
        theme_summaries = []
        theme_analysis = self.theme_repo.find_latest_by_audience_and_window(
            audience_id, window
        )
        if theme_analysis and theme_analysis.status == "ready":
            themes = self.theme_repo.get_themes(theme_analysis.id, limit=3)
            for theme in themes:
                ts = self.theme_summary_repo.find_by_theme_id(theme.id)
                if ts:
                    theme_summaries.append(ts)

        # Build context
        if pain_summary:
            intent_context = self._build_intent_context(pain_summary, theme_summaries)
            context_quality = "rich"
            sources_used = ["intent_classification", "theme_analysis"]

        # Run agent
        agent = create_intent_ask_agent()
        result = agent.invoke(
            {
                "intent_category": intent_category,
                "audience_name": audience.name,
                "community_names": community_names,
                "language": language,
                "question": question,
                "intent_context": intent_context,
                "context_quality": context_quality,
                "answer": None,
            }
        )

        answer = result.get("answer")
        final_context_quality = result.get("context_quality", context_quality)

        suggestion = None
        if final_context_quality == "limited":
            suggestion = (
                "Execute a classificação de intenções para obter respostas "
                "mais detalhadas e baseadas em dados reais."
            )

        response = {
            "answer": answer,
            "context_quality": final_context_quality,
            "sources_used": sources_used,
            "cached": False,
            "intent_category": intent_category,
            "suggestion": suggestion,
            "analysis_id": str(analysis_id) if analysis_id else None,
        }

        # Persist log first, then cache
        self._safe_create_log(
            analysis_id=analysis_id,
            audience_id=audience_id,
            user_id=user_id,
            intent_category=intent_category,
            question=question,
            answer=answer,
            context_quality=final_context_quality,
            cached=False,
        )

        # Cache the result
        self.cache_service.set(cache_key, TaskType.INTENT_QA, response)

        logger.info(
            "Intent Ask: answered for category '%s' (quality: %s)",
            intent_category,
            final_context_quality,
        )

        return response

    def _safe_create_log(self, **kwargs) -> None:
        """Persists the ask log without blocking the response on failure."""
        try:
            self.ask_repo.create_log(**kwargs)
        except Exception:
            logger.debug("Failed to persist intent ask log, skipping")
            try:
                self.db.rollback()
            except Exception:
                pass

    def _build_intent_context(
        self,
        pain_summary,
        theme_summaries: list | None = None,
    ) -> str:
        """Builds a text context from intent classification + theme data."""
        sections = []

        # 1. Description
        if pain_summary.description:
            sections.append(f"PAIN & ANGER OVERVIEW:\n{pain_summary.description}")

        # 2. Subcategories (emotions breakdown)
        if pain_summary.subcategories:
            lines = ["EMOTION BREAKDOWN:"]
            for emotion, count in sorted(
                pain_summary.subcategories.items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                lines.append(f"- {emotion}: {count} posts")
            sections.append("\n".join(lines))

        # 3. Topic Keywords
        if pain_summary.topic_keywords:
            lines = ["PAIN TOPIC KEYWORDS:"]
            for keyword, count in sorted(
                pain_summary.topic_keywords.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:20]:
                lines.append(f"- {keyword}: {count} mentions")
            sections.append("\n".join(lines))

        # 4. Pain Patterns (behavioral groups)
        if pain_summary.pain_patterns:
            lines = ["BEHAVIORAL PAIN PATTERNS:"]
            for pattern in pain_summary.pain_patterns:
                name = pattern.get("name", "")
                emoji = pattern.get("emoji", "")
                post_count = pattern.get("post_count", 0)
                total_upvotes = pattern.get("total_upvotes", 0)
                total_comments = pattern.get("total_comments", 0)
                lines.append(
                    f"- {emoji} {name} ({post_count} posts, "
                    f"{total_upvotes} upvotes, {total_comments} comments)"
                )
                # Include up to 3 sample submissions per pattern
                for sub in pattern.get("submissions", [])[:3]:
                    title = sub.get("title", "")
                    subreddit = sub.get("subreddit", "")
                    score = sub.get("score", 0)
                    lines.append(f'  * [{subreddit}, score:{score}] "{title}"')
                    if sub.get("body"):
                        body_preview = sub["body"][:200]
                        lines.append(f'    Body: "{body_preview}..."')
            sections.append("\n".join(lines))

        # 5. Top Subreddits
        if pain_summary.top_subreddits:
            lines = ["TOP SUBREDDITS FOR PAIN & ANGER:"]
            for sr in pain_summary.top_subreddits:
                name = sr.get("name", "")
                count = sr.get("count", 0)
                lines.append(f"- {name}: {count} posts")
            sections.append("\n".join(lines))

        # 6. Sample Posts
        if pain_summary.sample_posts:
            lines = ["SAMPLE POSTS:"]
            for post in pain_summary.sample_posts[:10]:
                title = post.get("title", "")
                subreddit = post.get("subreddit", "")
                lines.append(f'- [r/{subreddit}] "{title}"')
            sections.append("\n".join(lines))

        # 7. Theme Summaries (broader narrative context)
        if theme_summaries:
            lines = ["BROADER THEME CONTEXT:"]
            for ts in theme_summaries[:3]:
                if ts.narrative:
                    lines.append(f"\nTheme Narrative:\n{ts.narrative[:500]}")
                if ts.key_themes:
                    for kt in ts.key_themes[:3]:
                        theme_name = kt.get("theme", "")
                        desc = kt.get("description", "")
                        lines.append(f"  - {theme_name}: {desc}")
            sections.append("\n".join(lines))

        return "\n\n".join(sections)
