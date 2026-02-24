import json
import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.audience_topics.infra.repositories.audience_topic_repository import (
    AudienceTopicRepository,
)
from app.modules.shared.application.services.llm_cache_service import (
    LLMCacheService,
    TaskType,
)
from app.modules.topic_ask.application.use_cases.ask_topic_use_case.agent.ask_agent import (
    create_ask_agent,
)
from app.modules.topic_ask.infra.repositories.topic_ask_repository import (
    TopicAskRepository,
)
from app.modules.topic_deep_dive.infra.repositories.topic_deep_dive_repository import (
    TopicDeepDiveRepository,
)

logger = logging.getLogger(__name__)


class AskTopicUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.topic_repo = AudienceTopicRepository(db)
        self.deep_dive_repo = TopicDeepDiveRepository(db)
        self.ask_repo = TopicAskRepository(db)
        self.cache_service = LLMCacheService(db)

    def execute(
        self,
        topic_id: UUID,
        audience_id: UUID,
        user_id: UUID,
        question: str,
        language: str = "en",
    ) -> dict:
        """
        Responde uma pergunta sobre um tópico usando dados do Deep Dive como contexto.

        Returns:
            dict com answer, context_quality, cached, topic_name, sources_used, suggestion
        """
        topic = self.topic_repo.get_topic_by_id(topic_id)
        if not topic:
            return {"error": "Topic not found"}

        audience = self.audience_repo.find_by_id(audience_id)
        if not audience:
            return {"error": "Audience not found"}

        communities = self.audience_repo.get_communities(audience_id)
        community_names = [c.subreddit_name for c in communities]

        # Check cache
        cache_key = f"{topic_id}:{question.strip().lower()}"
        cached_result = self.cache_service.get(cache_key, TaskType.TOPIC_QA)
        if cached_result:
            logger.info("Ask Q&A: cache hit for topic '%s'", topic.name)
            self._safe_create_log(
                topic_id=topic_id,
                audience_id=audience_id,
                user_id=user_id,
                question=question,
                answer=cached_result.get("answer"),
                context_quality=cached_result.get("context_quality", "limited"),
                cached=True,
            )
            return {**cached_result, "cached": True}

        # Build deep dive context
        deep_dive_context = None
        context_quality = "limited"
        sources_used = ["topic_metadata"]

        latest_analysis = self.deep_dive_repo.find_latest_by_topic(topic_id)
        if latest_analysis and latest_analysis.status == "ready":
            deep_dive = self.deep_dive_repo.get_deep_dive(latest_analysis.id)
            if deep_dive:
                deep_dive_context = self._build_deep_dive_context(deep_dive)
                context_quality = "rich"
                sources_used = ["deep_dive"]

        # Run agent
        agent = create_ask_agent()
        result = agent.invoke({
            "topic_name": topic.name,
            "topic_description": topic.description or "",
            "audience_name": audience.name,
            "community_names": community_names,
            "language": language,
            "question": question,
            "deep_dive_context": deep_dive_context,
            "context_quality": context_quality,
            "answer": None,
        })

        answer = result.get("answer")
        final_context_quality = result.get("context_quality", context_quality)

        suggestion = None
        if final_context_quality == "limited":
            suggestion = (
                "Execute o Deep Dive neste tópico para obter respostas "
                "mais detalhadas e baseadas em dados reais."
            )

        response = {
            "answer": answer,
            "context_quality": final_context_quality,
            "sources_used": sources_used,
            "cached": False,
            "topic_name": topic.name,
            "suggestion": suggestion,
        }

        # Persist log first, then cache (log failure must not block the response)
        self._safe_create_log(
            topic_id=topic_id,
            audience_id=audience_id,
            user_id=user_id,
            question=question,
            answer=answer,
            context_quality=final_context_quality,
            cached=False,
        )

        # Cache the result (only after log succeeds or is safely skipped)
        self.cache_service.set(cache_key, TaskType.TOPIC_QA, response)

        logger.info(
            "Ask Q&A: answered for topic '%s' (quality: %s)",
            topic.name,
            final_context_quality,
        )

        return response

    def _safe_create_log(self, **kwargs) -> None:
        """Persists the ask log without blocking the response on failure."""
        try:
            self.ask_repo.create_log(**kwargs)
        except Exception:
            logger.debug("Failed to persist ask log, skipping")
            try:
                self.db.rollback()
            except Exception:
                pass

    def _build_deep_dive_context(self, deep_dive) -> str:
        """Builds a text context from the deep dive data stored in the database."""
        sections = []

        if deep_dive.summary:
            sections.append(f"SUMMARY:\n{deep_dive.summary}")

        if deep_dive.subtopics:
            lines = ["SUBTOPICS IDENTIFIED:"]
            for st in deep_dive.subtopics:
                name = st.get("name", "")
                desc = st.get("description", "")
                count = st.get("post_count", 0)
                lines.append(f"- {name} ({count} posts): {desc}")
            sections.append("\n".join(lines))

        if deep_dive.common_questions:
            lines = ["FREQUENTLY ASKED QUESTIONS:"]
            for q in deep_dive.common_questions:
                question = q.get("question", "")
                freq = q.get("frequency", "")
                ctx = q.get("example_context", "")
                lines.append(f"- [{freq}] \"{question}\"")
                if ctx:
                    lines.append(f"  Context: \"{ctx}\"")
            sections.append("\n".join(lines))

        if deep_dive.mentioned_products:
            lines = ["MENTIONED TOOLS/PRODUCTS:"]
            for p in deep_dive.mentioned_products:
                name = p.get("name", "")
                cat = p.get("category", "")
                sentiment = p.get("sentiment", "")
                mentions = p.get("mention_count", 0)
                context = p.get("context", "")
                lines.append(
                    f"- {name} ({cat}, sentiment: {sentiment}, {mentions} mentions): {context}"
                )
            sections.append("\n".join(lines))

        if deep_dive.representative_posts:
            lines = ["REPRESENTATIVE POSTS:"]
            for p in deep_dive.representative_posts:
                title = p.get("title", "")
                sub = p.get("subreddit", "")
                score = p.get("score", 0)
                excerpt = p.get("excerpt", "")
                lines.append(f"- [r/{sub}, score:{score}] \"{title}\"")
                if excerpt:
                    lines.append(f"  Excerpt: \"{excerpt}\"")
            sections.append("\n".join(lines))

        if deep_dive.actionable_insights:
            lines = ["ACTIONABLE INSIGHTS:"]
            for i in deep_dive.actionable_insights:
                insight = i.get("insight", "")
                itype = i.get("type", "")
                confidence = i.get("confidence", "")
                lines.append(f"- [{itype}, {confidence} confidence] {insight}")
            sections.append("\n".join(lines))

        return "\n\n".join(sections)
