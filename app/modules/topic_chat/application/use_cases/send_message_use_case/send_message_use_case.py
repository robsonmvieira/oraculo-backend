import json
import logging
import os
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from app.modules.audience_topics.infra.repositories.audience_topic_repository import (
    AudienceTopicRepository,
)
from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.topic_chat.application.use_cases.send_message_use_case.agent.chat_agent import (
    build_prompt_messages,
    create_chat_agent,
)
from app.modules.topic_chat.infra.repositories.topic_conversation_message_repository import (
    TopicConversationMessageRepository,
)
from app.modules.topic_chat.infra.repositories.topic_conversation_repository import (
    TopicConversationRepository,
)
from app.modules.topic_deep_dive.infra.repositories.topic_deep_dive_repository import (
    TopicDeepDiveRepository,
)
from app.modules.topic_patterns.infra.repositories.topic_pattern_repository import (
    TopicPatternRepository,
)
from app.modules.shared.infra.cache.redit_cache import RedisCache
from app.modules.topic_sentiment.infra.repositories.topic_sentiment_repository import (
    TopicSentimentRepository,
)

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 40
MAX_MESSAGES_PER_CONVERSATION = 100
RATE_LIMIT_MESSAGES = int(os.getenv("RATE_LIMIT_MESSAGES", "20"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))


class SendMessageUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.topic_repo = AudienceTopicRepository(db)
        self.deep_dive_repo = TopicDeepDiveRepository(db)
        self.sentiment_repo = TopicSentimentRepository(db)
        self.pattern_repo = TopicPatternRepository(db)
        self.conversation_repo = TopicConversationRepository(db)
        self.message_repo = TopicConversationMessageRepository(db)

    def execute(
        self,
        conversation_id: UUID,
        question: str,
        language: str = "en",
        user_id: UUID | None = None,
    ) -> dict:
        """
        Envia uma mensagem na conversa e retorna a resposta da IA.

        Returns:
            dict com answer, context_quality, message_id, conversation_id
        """
        conversation = self.conversation_repo.find_by_id(conversation_id)
        if not conversation:
            return {"error": "Conversation not found"}

        # Rate limit check (before any heavy work)
        effective_user_id = user_id or conversation.user_id
        rate_error = self._check_rate_limit(effective_user_id)
        if rate_error:
            return rate_error

        topic = self.topic_repo.get_topic_by_id(conversation.topic_id)
        if not topic:
            return {"error": "Topic not found"}

        audience = self.audience_repo.find_by_id(conversation.audience_id)
        if not audience:
            return {"error": "Audience not found"}

        communities = self.audience_repo.get_communities(conversation.audience_id)
        community_names = [c.subreddit_name for c in communities]

        # Check message limit before persisting
        limit_error = self._check_message_limit(conversation_id)
        if limit_error:
            return limit_error

        # Persist user message
        self.message_repo.create(
            conversation_id=conversation_id,
            role="user",
            content=question,
        )

        # Load conversation history (with summarization for long conversations)
        all_records = self.message_repo.list_all_by_conversation(conversation_id)
        all_dicts = [{"role": msg.role, "content": msg.content} for msg in all_records]

        conversation_summary = None
        if len(all_dicts) > MAX_HISTORY_MESSAGES:
            old_messages = all_dicts[:-MAX_HISTORY_MESSAGES]
            messages = all_dicts[-MAX_HISTORY_MESSAGES:]
            conversation_summary = self._summarize_conversation(
                old_messages, topic.name
            )
        else:
            messages = all_dicts

        # Build context from all available sources
        deep_dive_context = self._load_deep_dive_context(conversation.topic_id)
        sentiment_context = self._load_sentiment_context(conversation.topic_id)
        pattern_context = self._load_pattern_context(conversation.audience_id)

        context_quality = self._compute_context_quality(
            deep_dive_context, sentiment_context, pattern_context
        )

        # Run agent with conversation history
        agent = create_chat_agent()
        result = agent.invoke(
            {
                "topic_name": topic.name,
                "topic_description": topic.description or "",
                "audience_name": audience.name,
                "community_names": community_names,
                "language": language,
                "deep_dive_context": deep_dive_context,
                "sentiment_context": sentiment_context,
                "pattern_context": pattern_context,
                "conversation_summary": conversation_summary,
                "context_quality": context_quality,
                "messages": messages,
                "answer": None,
            }
        )

        answer = result.get("answer", "")
        final_context_quality = result.get("context_quality", context_quality)

        # Persist assistant message
        assistant_msg = self.message_repo.create(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            context_quality=final_context_quality,
        )

        # Update conversation metadata
        self.conversation_repo.update_context_quality(
            conversation_id, final_context_quality
        )
        self.conversation_repo.touch(conversation_id)

        # Generate smart title and/or follow-up suggestions
        needs_title = not conversation.title
        title_and_suggestions = self._generate_title_and_suggestions(
            question=question,
            answer=answer,
            topic_name=topic.name,
            language=language,
            generate_title=needs_title,
        )

        if needs_title and title_and_suggestions.get("title"):
            self.conversation_repo.update_title(
                conversation_id, title_and_suggestions["title"]
            )

        follow_up_suggestions = title_and_suggestions.get("follow_up_suggestions", [])

        suggestion = None
        if final_context_quality == "limited":
            suggestion = (
                "Execute o Deep Dive neste topico para obter respostas "
                "mais detalhadas e baseadas em dados reais."
            )

        logger.info(
            "Topic Chat: answered in conversation '%s' (quality: %s)",
            conversation_id,
            final_context_quality,
        )

        return {
            "answer": answer,
            "context_quality": final_context_quality,
            "message_id": str(assistant_msg.id),
            "conversation_id": str(conversation_id),
            "suggestion": suggestion,
            "follow_up_suggestions": follow_up_suggestions,
        }

    async def execute_streaming(
        self,
        conversation_id: UUID,
        question: str,
        language: str = "en",
        user_id: UUID | None = None,
    ):
        """
        Streaming version of execute(). Yields SSE-formatted strings.

        Events:
          - event: token  — partial content token
          - event: done   — full metadata (answer, context_quality, message_id, etc.)
          - event: error  — error message
        """
        # Phase 1: Synchronous setup
        conversation = self.conversation_repo.find_by_id(conversation_id)
        if not conversation:
            yield f"event: error\ndata: {json.dumps({'error': 'Conversation not found'})}\n\n"
            return

        # Rate limit check (before any heavy work)
        effective_user_id = user_id or conversation.user_id
        rate_error = self._check_rate_limit(effective_user_id)
        if rate_error:
            yield f"event: error\ndata: {json.dumps(rate_error)}\n\n"
            return

        topic = self.topic_repo.get_topic_by_id(conversation.topic_id)
        if not topic:
            yield f"event: error\ndata: {json.dumps({'error': 'Topic not found'})}\n\n"
            return

        audience = self.audience_repo.find_by_id(conversation.audience_id)
        if not audience:
            yield f"event: error\ndata: {json.dumps({'error': 'Audience not found'})}\n\n"
            return

        communities = self.audience_repo.get_communities(conversation.audience_id)
        community_names = [c.subreddit_name for c in communities]

        # Check message limit before persisting
        limit_error = self._check_message_limit(conversation_id)
        if limit_error:
            yield f"event: error\ndata: {json.dumps(limit_error)}\n\n"
            return

        # Persist user message
        self.message_repo.create(
            conversation_id=conversation_id,
            role="user",
            content=question,
        )

        # Load conversation history (with summarization)
        all_records = self.message_repo.list_all_by_conversation(conversation_id)
        all_dicts = [{"role": msg.role, "content": msg.content} for msg in all_records]

        conversation_summary = None
        if len(all_dicts) > MAX_HISTORY_MESSAGES:
            old_messages = all_dicts[:-MAX_HISTORY_MESSAGES]
            messages = all_dicts[-MAX_HISTORY_MESSAGES:]
            conversation_summary = self._summarize_conversation(
                old_messages, topic.name
            )
        else:
            messages = all_dicts

        # Build context from all available sources
        deep_dive_context = self._load_deep_dive_context(conversation.topic_id)
        sentiment_context = self._load_sentiment_context(conversation.topic_id)
        pattern_context = self._load_pattern_context(conversation.audience_id)

        context_quality = self._compute_context_quality(
            deep_dive_context, sentiment_context, pattern_context
        )

        # Phase 2: Build prompt and stream tokens
        langchain_messages = build_prompt_messages(
            topic_name=topic.name,
            topic_description=topic.description or "",
            audience_name=audience.name,
            community_names=community_names,
            language=language,
            deep_dive_context=deep_dive_context,
            sentiment_context=sentiment_context,
            pattern_context=pattern_context,
            context_quality=context_quality,
            conversation_summary=conversation_summary,
            messages=messages,
        )

        llm = ChatOpenAI(
            model=os.getenv("MODEL_NAME", "gpt-5-nano-2025-08-07"),
            max_completion_tokens=16384,
            streaming=True,
        )

        full_answer = []
        async for chunk in llm.astream(langchain_messages):
            token = chunk.content
            if token:
                full_answer.append(token)
                yield f"event: token\ndata: {json.dumps({'content': token})}\n\n"

        answer = "".join(full_answer)

        # Phase 3: Post-streaming persistence
        assistant_msg = self.message_repo.create(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            context_quality=context_quality,
        )

        self.conversation_repo.update_context_quality(conversation_id, context_quality)
        self.conversation_repo.touch(conversation_id)

        # Generate smart title and/or follow-up suggestions
        needs_title = not conversation.title
        title_and_suggestions = self._generate_title_and_suggestions(
            question=question,
            answer=answer,
            topic_name=topic.name,
            language=language,
            generate_title=needs_title,
        )

        if needs_title and title_and_suggestions.get("title"):
            self.conversation_repo.update_title(
                conversation_id, title_and_suggestions["title"]
            )

        follow_up_suggestions = title_and_suggestions.get("follow_up_suggestions", [])

        suggestion = None
        if context_quality == "limited":
            suggestion = (
                "Execute o Deep Dive neste topico para obter respostas "
                "mais detalhadas e baseadas em dados reais."
            )

        logger.info(
            "Topic Chat (streaming): answered in conversation '%s' (quality: %s)",
            conversation_id,
            context_quality,
        )

        done_data = {
            "answer": answer,
            "context_quality": context_quality,
            "message_id": str(assistant_msg.id),
            "conversation_id": str(conversation_id),
            "suggestion": suggestion,
            "follow_up_suggestions": follow_up_suggestions,
        }
        yield f"event: done\ndata: {json.dumps(done_data)}\n\n"

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
                lines.append(f'- [{freq}] "{question}"')
                if ctx:
                    lines.append(f'  Context: "{ctx}"')
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
                lines.append(f'- [r/{sub}, score:{score}] "{title}"')
                if excerpt:
                    lines.append(f'  Excerpt: "{excerpt}"')
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

    # ------------------------------------------------------------------
    # Context loaders
    # ------------------------------------------------------------------

    def _load_deep_dive_context(self, topic_id) -> str | None:
        latest = self.deep_dive_repo.find_latest_by_topic(topic_id)
        if latest and latest.status == "ready":
            deep_dive = self.deep_dive_repo.get_deep_dive(latest.id)
            if deep_dive:
                return self._build_deep_dive_context(deep_dive)
        return None

    def _load_sentiment_context(self, topic_id) -> str | None:
        latest = self.sentiment_repo.find_latest_by_topic(topic_id)
        if latest and latest.status == "ready":
            sentiment = self.sentiment_repo.get_sentiment(latest.id)
            if sentiment:
                return self._build_sentiment_context(sentiment)
        return None

    def _load_pattern_context(self, audience_id) -> str | None:
        latest = self.pattern_repo.find_latest_by_audience(audience_id)
        if latest and latest.status == "ready":
            pattern = self.pattern_repo.get_pattern(latest.id)
            if pattern:
                return self._build_pattern_context(pattern)
        return None

    @staticmethod
    def _compute_context_quality(
        deep_dive_ctx: str | None,
        sentiment_ctx: str | None,
        pattern_ctx: str | None,
    ) -> str:
        count = sum(1 for ctx in (deep_dive_ctx, sentiment_ctx, pattern_ctx) if ctx)
        if count >= 2:
            return "rich"
        if count == 1:
            return "partial"
        return "limited"

    # ------------------------------------------------------------------
    # Context builders — Sentiment
    # ------------------------------------------------------------------

    def _build_sentiment_context(self, sentiment) -> str:
        """Builds a text context from sentiment analysis data."""
        sections = []

        if sentiment.overall_sentiment:
            s = sentiment.overall_sentiment
            sections.append(
                f"OVERALL SENTIMENT:\n"
                f"Score: {s.get('score', 'N/A')}, "
                f"Positive: {s.get('positive_ratio', 'N/A')}, "
                f"Negative: {s.get('negative_ratio', 'N/A')}, "
                f"Neutral: {s.get('neutral_ratio', 'N/A')}"
            )

        if sentiment.emotional_map:
            lines = ["EMOTIONAL MAP:"]
            for e in sentiment.emotional_map:
                pct = e.get("percentage", 0)
                pct_str = f"{pct * 100:.0f}%" if isinstance(pct, (int, float)) else pct
                lines.append(
                    f"- {e.get('emotion', '')} (intensity: {e.get('intensity', '')}, "
                    f"{pct_str}): {e.get('example', '')}"
                )
            sections.append("\n".join(lines))

        if sentiment.pain_points:
            lines = ["PAIN POINTS:"]
            for p in sentiment.pain_points:
                lines.append(
                    f"- [{p.get('severity', '')}] {p.get('pain', '')}: "
                    f'"{p.get("verbatim", "")}"'
                )
            sections.append("\n".join(lines))

        if sentiment.tension_points:
            lines = ["TENSION POINTS:"]
            for t in sentiment.tension_points:
                lines.append(
                    f"- {t.get('topic', '')} "
                    f"(for: {t.get('for_ratio', '')}, against: {t.get('against_ratio', '')}): "
                    f"{t.get('summary', '')}"
                )
            sections.append("\n".join(lines))

        if sentiment.sentiment_drivers:
            lines = ["SENTIMENT DRIVERS:"]
            for polarity in ("positive", "negative"):
                for d in sentiment.sentiment_drivers.get(polarity, []):
                    lines.append(
                        f"- [{polarity}] {d.get('driver', '')} "
                        f"({d.get('frequency', '')} freq, {d.get('mentions', 0)} mentions)"
                    )
            sections.append("\n".join(lines))

        if sentiment.sentiment_opportunities:
            lines = ["SENTIMENT OPPORTUNITIES:"]
            for o in sentiment.sentiment_opportunities:
                lines.append(
                    f"- [{o.get('confidence', '')}] {o.get('opportunity', '')} "
                    f"(based on: {o.get('based_on', '')})"
                )
            sections.append("\n".join(lines))

        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # Context builders — Patterns
    # ------------------------------------------------------------------

    def _build_pattern_context(self, pattern) -> str:
        """Builds a text context from cross-topic pattern data."""
        sections = []

        if pattern.summary:
            sections.append(f"PATTERN SUMMARY:\n{pattern.summary}")

        if pattern.co_occurrences:
            lines = ["CO-OCCURRENCES:"]
            for c in pattern.co_occurrences:
                lines.append(
                    f"- Topics {c.get('topics', [])} ({c.get('frequency', '')}): "
                    f"{c.get('context', '')}"
                )
            sections.append("\n".join(lines))

        if pattern.unanswered_questions:
            lines = ["UNANSWERED QUESTIONS:"]
            for q in pattern.unanswered_questions:
                lines.append(
                    f'- [{q.get("frequency", "")}] "{q.get("question", "")}" '
                    f"(communities: {q.get('communities', [])})"
                )
            sections.append("\n".join(lines))

        if pattern.cross_community_gaps:
            lines = ["CROSS-COMMUNITY GAPS:"]
            for g in pattern.cross_community_gaps:
                lines.append(
                    f"- {g.get('topic', '')}: discussed in {g.get('discussed_in', [])}, "
                    f"missing in {g.get('missing_in', [])} — {g.get('opportunity', '')}"
                )
            sections.append("\n".join(lines))

        if pattern.content_opportunities:
            lines = ["CONTENT OPPORTUNITIES:"]
            for o in pattern.content_opportunities:
                lines.append(
                    f"- [{o.get('type', '')}, {o.get('confidence', '')}] "
                    f"{o.get('opportunity', '')} (based on: {o.get('based_on', '')})"
                )
            sections.append("\n".join(lines))

        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # Conversation summarization
    # ------------------------------------------------------------------

    def _summarize_conversation(self, messages: list[dict], topic_name: str) -> str:
        """Summarize older messages into a concise context paragraph."""
        conversation_text = "\n".join(
            f"[{m['role']}]: {m['content'][:500]}" for m in messages
        )

        llm = ChatOpenAI(
            model=os.getenv("MODEL_NAME", "gpt-5-nano-2025-08-07"),
            max_completion_tokens=1024,
        )

        summary_messages = [
            SystemMessage(
                content=(
                    "You are a conversation summarizer. Compress the following conversation about "
                    f"the topic '{topic_name}' into a concise summary (2-4 paragraphs max). "
                    "Preserve key questions asked, insights given, decisions made, and any "
                    "specific data points or recommendations discussed. Do not lose important details."
                )
            ),
            HumanMessage(content=conversation_text),
        ]

        response = llm.invoke(summary_messages)

        logger.info(
            "Topic Chat: summarized %d old messages for topic '%s'",
            len(messages),
            topic_name,
        )

        return response.content.strip()

    # ------------------------------------------------------------------
    # Message limit check
    # ------------------------------------------------------------------

    def _check_message_limit(self, conversation_id: UUID) -> dict | None:
        """
        Verifica se a conversa atingiu o limite de mensagens.

        Returns:
            dict com erro se limite atingido, None caso contrario
        """
        count = self.message_repo.count_by_conversation(conversation_id)
        if count >= MAX_MESSAGES_PER_CONVERSATION:
            return {
                "error": "message_limit_reached",
                "detail": (
                    f"This conversation has reached the maximum of "
                    f"{MAX_MESSAGES_PER_CONVERSATION} messages. "
                    f"Please create a new conversation to continue."
                ),
                "message_count": count,
            }
        return None

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _check_rate_limit(self, user_id: UUID) -> dict | None:
        """
        Verifica rate limit por usuario via Redis.

        Fail-open: se Redis estiver indisponivel, permite o request.

        Returns:
            dict com erro se limite atingido, None caso contrario
        """
        try:
            cache = RedisCache()
            key = f"rate_limit:topic_chat:{user_id}"
            count = cache.increment(key, ttl=RATE_LIMIT_WINDOW_SECONDS)
            if count > RATE_LIMIT_MESSAGES:
                return {
                    "error": "rate_limit_exceeded",
                    "detail": (
                        f"You have exceeded the limit of {RATE_LIMIT_MESSAGES} "
                        f"messages per minute. Please wait before sending "
                        f"another message."
                    ),
                    "retry_after_seconds": RATE_LIMIT_WINDOW_SECONDS,
                }
        except Exception:
            logger.warning("Rate limit check failed (Redis unavailable), allowing request")
        return None

    # ------------------------------------------------------------------
    # Smart title and follow-up suggestions
    # ------------------------------------------------------------------

    def _generate_title_and_suggestions(
        self,
        question: str,
        answer: str,
        topic_name: str,
        language: str,
        generate_title: bool = False,
    ) -> dict:
        """
        Gera titulo inteligente e/ou sugestoes de follow-up via LLM.

        Quando generate_title=True (1a mensagem), gera titulo + sugestoes
        em uma unica chamada. Nas demais mensagens, gera apenas sugestoes.

        Returns:
            dict com 'title' (str | None) e 'follow_up_suggestions' (list[str])
        """
        if generate_title:
            instruction = (
                "Based on the user's question and the AI answer about the topic "
                f"'{topic_name}', generate:\n"
                "1. A concise conversation title (max 60 chars, descriptive, no quotes)\n"
                "2. Exactly 3 follow-up question suggestions (max 80 chars each)\n\n"
                "Respond in valid JSON:\n"
                '{"title": "...", "follow_up_suggestions": ["...", "...", "..."]}'
            )
        else:
            instruction = (
                "Based on the user's question and the AI answer about the topic "
                f"'{topic_name}', generate exactly 3 follow-up question suggestions "
                "(max 80 chars each) that would deepen the analysis.\n\n"
                "Respond in valid JSON:\n"
                '{"follow_up_suggestions": ["...", "...", "..."]}'
            )

        from app.modules.shared.application.helpers.language_directive import (
            get_language_directive,
        )

        language_directive = get_language_directive(language)

        llm = ChatOpenAI(
            model=os.getenv("MODEL_NAME", "gpt-5-nano-2025-08-07"),
            max_completion_tokens=256,
            model_kwargs={"response_format": {"type": "json_object"}},
        )

        prompt_messages = [
            SystemMessage(content=instruction + language_directive),
            HumanMessage(
                content=f"USER QUESTION: {question}\n\nAI ANSWER: {answer[:1500]}"
            ),
        ]

        try:
            response = llm.invoke(prompt_messages)
            data = json.loads(response.content)
            return {
                "title": data.get("title") if generate_title else None,
                "follow_up_suggestions": data.get("follow_up_suggestions", [])[:3],
            }
        except Exception:
            logger.warning("Failed to generate title/suggestions, using fallback")
            fallback_title = None
            if generate_title:
                fallback_title = question[:100].strip()
                if len(question) > 100:
                    fallback_title += "..."
            return {
                "title": fallback_title,
                "follow_up_suggestions": [],
            }
