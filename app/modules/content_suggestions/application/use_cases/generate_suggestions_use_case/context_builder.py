"""Coleta e compacta dados de todos os módulos analíticos para o agente de sugestões."""

import json
import logging
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

MAX_CONTEXT_CHARS = 60_000


class ContextBuilder:
    """Coleta outputs dos módulos analíticos e monta contexto compactado."""

    def __init__(self, db: Session):
        self.db = db

    def build(
        self, audience_id: UUID
    ) -> tuple[str, list[str], list[dict], dict[str, str | None]]:
        """
        Coleta dados de todos os módulos disponíveis e monta contexto.

        Returns:
            tuple: (assembled_context, modules_available, topic_contexts, analysis_ids)
        """
        sections = []
        modules_available = []
        topic_contexts = []
        analysis_ids: dict[str, str | None] = {}

        # 1. Topics (obrigatório)
        topics_section, topics_data, topic_analysis_id = self._collect_topics(audience_id)
        analysis_ids["topics"] = topic_analysis_id
        if topics_section:
            sections.append(topics_section)
            modules_available.append("topics")
            topic_contexts = topics_data

        # 2. Deep Dive
        dd_section, dd_ids = self._collect_deep_dives(topic_contexts)
        analysis_ids["deep_dive"] = dd_ids
        if dd_section:
            sections.append(dd_section)
            modules_available.append("deep_dive")

        # 3. Patterns
        patterns_section, pattern_id = self._collect_patterns(audience_id)
        analysis_ids["patterns"] = pattern_id
        if patterns_section:
            sections.append(patterns_section)
            modules_available.append("patterns")

        # 4. Behavioral Patterns
        bp_section, bp_ids = self._collect_behavioral_patterns(topic_contexts)
        analysis_ids["behavioral_patterns"] = bp_ids
        if bp_section:
            sections.append(bp_section)
            modules_available.append("behavioral_patterns")

        # 5. Sentiment
        sent_section, sent_ids = self._collect_sentiment(topic_contexts)
        analysis_ids["sentiment"] = sent_ids
        if sent_section:
            sections.append(sent_section)
            modules_available.append("sentiment")

        # 6. Themes
        theme_section, theme_id = self._collect_themes(audience_id)
        analysis_ids["themes"] = theme_id
        if theme_section:
            sections.append(theme_section)
            modules_available.append("themes")

        # 7. Intent Classification
        intent_section, intent_id = self._collect_intents(audience_id)
        analysis_ids["intent_classification"] = intent_id
        if intent_section:
            sections.append(intent_section)
            modules_available.append("intent_classification")

        # 8. Keywords
        kw_section, kw_id = self._collect_keywords(audience_id)
        analysis_ids["keywords"] = kw_id
        if kw_section:
            sections.append(kw_section)
            modules_available.append("keywords")

        # 9. Alerts
        alerts_section = self._collect_alerts(audience_id)
        if alerts_section:
            sections.append(alerts_section)
            modules_available.append("alerts")

        # 10. Theme Summaries
        summary_section = self._collect_theme_summaries(audience_id)
        if summary_section:
            sections.append(summary_section)
            modules_available.append("theme_summaries")

        # Montar contexto final respeitando limite
        assembled = "\n\n---\n\n".join(sections)
        if len(assembled) > MAX_CONTEXT_CHARS:
            assembled = assembled[:MAX_CONTEXT_CHARS] + "\n\n[Context truncated due to size limit]"

        logger.info(
            "Context built: %d modules, %d topics, %d chars",
            len(modules_available),
            len(topic_contexts),
            len(assembled),
        )

        return assembled, modules_available, topic_contexts, analysis_ids

    def _collect_topics(
        self, audience_id: UUID
    ) -> tuple[str, list[dict], str | None]:
        """Coleta tópicos rankeados da audiência."""
        try:
            from app.modules.audience_topics.infra.repositories.audience_topic_repository import (
                AudienceTopicRepository,
            )

            repo = AudienceTopicRepository(self.db)
            analysis = repo.find_latest_ready(audience_id)
            if not analysis:
                return "", [], None

            topics = repo.get_topics(analysis.id)
            if not topics:
                return "", [], str(analysis.id)

            topic_data = []
            lines = ["## TOPICS (ranked by relevance)"]
            for t in topics[:15]:
                communities = t.communities or []
                comm_names = [c.get("name", "") for c in communities] if isinstance(communities, list) else []
                lines.append(
                    f"- **{t.name}**: {t.description or 'N/A'} | "
                    f"posts: {t.post_count or 0}, growth: {t.growth_percentage or 'N/A'}%, "
                    f"mentions: {t.mention_frequency or 0}, "
                    f"communities: {', '.join(comm_names)}"
                )
                topic_data.append({
                    "topic_id": str(t.id),
                    "topic_name": t.name,
                    "growth_percentage": t.growth_percentage,
                    "mention_frequency": t.mention_frequency or 0,
                    "post_count": t.post_count or 0,
                    "communities": comm_names,
                })

            return "\n".join(lines), topic_data, str(analysis.id)
        except Exception:
            logger.debug("Failed to collect topics", exc_info=True)
            return "", [], None

    def _collect_deep_dives(
        self, topic_contexts: list[dict]
    ) -> tuple[str, str | None]:
        """Coleta deep dives dos tópicos."""
        try:
            from app.modules.topic_deep_dive.infra.repositories.topic_deep_dive_repository import (
                TopicDeepDiveRepository,
            )

            repo = TopicDeepDiveRepository(self.db)
            lines = ["## DEEP DIVE INSIGHTS"]
            found_any = False
            first_id = None

            for tc in topic_contexts[:5]:
                topic_id = tc["topic_id"]
                analysis = repo.find_latest_by_topic(UUID(topic_id))
                if not analysis or analysis.status != "ready":
                    continue

                dd = repo.get_deep_dive(analysis.id)
                if not dd:
                    continue

                if not first_id:
                    first_id = str(analysis.id)
                found_any = True

                lines.append(f"\n### Topic: {tc['topic_name']}")
                if dd.common_questions:
                    qs = dd.common_questions[:5] if isinstance(dd.common_questions, list) else []
                    if qs:
                        lines.append(f"  Common questions: {json.dumps(qs)}")
                if dd.mentioned_products:
                    prods = dd.mentioned_products[:5] if isinstance(dd.mentioned_products, list) else []
                    if prods:
                        lines.append(f"  Mentioned products: {json.dumps(prods)}")
                if dd.actionable_insights:
                    insights = dd.actionable_insights[:3] if isinstance(dd.actionable_insights, list) else []
                    if insights:
                        lines.append(f"  Actionable insights: {json.dumps(insights)}")

            return ("\n".join(lines), first_id) if found_any else ("", None)
        except Exception:
            logger.debug("Failed to collect deep dives", exc_info=True)
            return "", None

    def _collect_patterns(
        self, audience_id: UUID
    ) -> tuple[str, str | None]:
        """Coleta padrões cross-tópico."""
        try:
            from app.modules.topic_patterns.infra.repositories.topic_pattern_repository import (
                TopicPatternRepository,
            )

            repo = TopicPatternRepository(self.db)
            analysis = repo.find_latest_by_audience(audience_id)
            if not analysis or analysis.status != "ready":
                return "", None

            p = repo.get_pattern(analysis.id)
            if not p:
                return "", str(analysis.id)

            lines = ["## CROSS-TOPIC PATTERNS"]
            if p.unanswered_questions:
                uqs = p.unanswered_questions[:5] if isinstance(p.unanswered_questions, list) else []
                if uqs:
                    lines.append(f"  Unanswered questions: {json.dumps(uqs)}")
            if p.cross_community_gaps:
                gaps = p.cross_community_gaps[:3] if isinstance(p.cross_community_gaps, list) else []
                if gaps:
                    lines.append(f"  Cross-community gaps: {json.dumps(gaps)}")
            if p.content_opportunities:
                opps = p.content_opportunities[:3] if isinstance(p.content_opportunities, list) else []
                if opps:
                    lines.append(f"  Content opportunities: {json.dumps(opps)}")

            return "\n".join(lines), str(analysis.id)
        except Exception:
            logger.debug("Failed to collect patterns", exc_info=True)
            return "", None

    def _collect_behavioral_patterns(
        self, topic_contexts: list[dict]
    ) -> tuple[str, str | None]:
        """Coleta padrões comportamentais."""
        try:
            from app.modules.topic_behavioral_patterns.infra.repositories.topic_behavioral_pattern_repository import (
                TopicBehavioralPatternRepository,
            )

            repo = TopicBehavioralPatternRepository(self.db)
            lines = ["## BEHAVIORAL PATTERNS"]
            found_any = False
            first_id = None

            for tc in topic_contexts[:5]:
                topic_id = tc["topic_id"]
                analysis = repo.find_latest_by_topic(UUID(topic_id))
                if not analysis or analysis.status != "ready":
                    continue

                bp = repo.get_behavioral_pattern(analysis.id)
                if not bp:
                    continue

                if not first_id:
                    first_id = str(analysis.id)
                found_any = True

                lines.append(f"\n### Topic: {tc['topic_name']}")
                if bp.workaround_patterns:
                    wks = bp.workaround_patterns[:3] if isinstance(bp.workaround_patterns, list) else []
                    if wks:
                        lines.append(f"  Workarounds: {json.dumps(wks)}")
                if bp.friction_patterns:
                    fps = bp.friction_patterns[:3] if isinstance(bp.friction_patterns, list) else []
                    if fps:
                        lines.append(f"  Frictions: {json.dumps(fps)}")
                if bp.demand_signals:
                    ds = bp.demand_signals[:3] if isinstance(bp.demand_signals, list) else []
                    if ds:
                        lines.append(f"  Demand signals: {json.dumps(ds)}")

            return ("\n".join(lines), first_id) if found_any else ("", None)
        except Exception:
            logger.debug("Failed to collect behavioral patterns", exc_info=True)
            return "", None

    def _collect_sentiment(
        self, topic_contexts: list[dict]
    ) -> tuple[str, str | None]:
        """Coleta análise de sentimento."""
        try:
            from app.modules.topic_sentiment.infra.repositories.topic_sentiment_repository import (
                TopicSentimentRepository,
            )

            repo = TopicSentimentRepository(self.db)
            lines = ["## SENTIMENT ANALYSIS"]
            found_any = False
            first_id = None

            for tc in topic_contexts[:5]:
                topic_id = tc["topic_id"]
                analysis = repo.find_latest_by_topic(UUID(topic_id))
                if not analysis or analysis.status != "ready":
                    continue

                s = repo.get_sentiment(analysis.id)
                if not s:
                    continue

                if not first_id:
                    first_id = str(analysis.id)
                found_any = True

                lines.append(f"\n### Topic: {tc['topic_name']}")
                if s.emotional_map:
                    em = s.emotional_map[:5] if isinstance(s.emotional_map, list) else s.emotional_map
                    lines.append(f"  Emotional map: {json.dumps(em)}")
                if s.pain_points:
                    pp = s.pain_points[:5] if isinstance(s.pain_points, list) else s.pain_points
                    lines.append(f"  Pain points: {json.dumps(pp)}")
                if s.sentiment_opportunities:
                    so = s.sentiment_opportunities[:3] if isinstance(s.sentiment_opportunities, list) else s.sentiment_opportunities
                    lines.append(f"  Opportunities: {json.dumps(so)}")

            return ("\n".join(lines), first_id) if found_any else ("", None)
        except Exception:
            logger.debug("Failed to collect sentiment", exc_info=True)
            return "", None

    def _collect_themes(
        self, audience_id: UUID
    ) -> tuple[str, str | None]:
        """Coleta temas temporais."""
        try:
            from app.modules.theme_analysis.infra.repositories.theme_analysis_repository import (
                ThemeAnalysisRepository,
            )

            repo = ThemeAnalysisRepository(self.db)
            analysis = repo.find_latest_by_audience_and_window(audience_id, "week")
            if not analysis or analysis.status != "ready":
                return "", None

            themes = repo.get_themes(analysis.id)
            if not themes:
                return "", str(analysis.id)

            lines = ["## WEEKLY THEMES"]
            for t in themes[:5]:
                lines.append(
                    f"- **{t.name}**: posts={t.post_count or 0}, "
                    f"engagement={t.engagement_score or 0:.1f}, "
                    f"keywords={json.dumps(t.top_keywords or [])}"
                )

            return "\n".join(lines), str(analysis.id)
        except Exception:
            logger.debug("Failed to collect themes", exc_info=True)
            return "", None

    def _collect_intents(
        self, audience_id: UUID
    ) -> tuple[str, str | None]:
        """Coleta classificação de intenções."""
        try:
            from app.modules.intent_classification.infra.repositories.intent_classification_repository import (
                IntentClassificationRepository,
            )

            repo = IntentClassificationRepository(self.db)
            analysis = repo.find_latest_by_audience_and_window(audience_id, "week")
            if not analysis or analysis.status != "ready":
                return "", None

            summaries = repo.get_intent_summaries(analysis.id)
            if not summaries:
                return "", str(analysis.id)

            total = analysis.total_posts_classified or 0
            lines = ["## INTENT CLASSIFICATION"]
            for s in summaries:
                pct = round((s.post_count / total) * 100, 1) if total > 0 else 0
                lines.append(f"- {s.intent_category}: {s.post_count} posts ({pct}%) — {s.description or 'N/A'}")

            return "\n".join(lines), str(analysis.id)
        except Exception:
            logger.debug("Failed to collect intents", exc_info=True)
            return "", None

    def _collect_keywords(
        self, audience_id: UUID
    ) -> tuple[str, str | None]:
        """Coleta keywords da audiência."""
        try:
            from app.modules.audience_keywords.infra.repositories.audience_keyword_repository import (
                AudienceKeywordRepository,
            )

            repo = AudienceKeywordRepository(self.db)
            analysis = repo.find_latest_ready(audience_id)
            if not analysis:
                return "", None

            keywords = repo.get_keywords(analysis.id)
            if not keywords:
                return "", str(analysis.id)

            lines = ["## AUDIENCE KEYWORDS"]
            by_category: dict[str, list[str]] = {}
            for kw in keywords[:30]:
                cat = kw.category or "general"
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(f"{kw.keyword} (relevance: {kw.relevance_score or 0:.1f})")

            for cat, kws in by_category.items():
                lines.append(f"- {cat}: {', '.join(kws[:10])}")

            return "\n".join(lines), str(analysis.id)
        except Exception:
            logger.debug("Failed to collect keywords", exc_info=True)
            return "", None

    def _collect_alerts(self, audience_id: UUID) -> str:
        """Coleta alertas recentes."""
        try:
            from app.modules.topic_alerts.domain.entities.topic_alert import TopicAlert

            alerts = (
                self.db.query(TopicAlert)
                .filter(
                    TopicAlert.audience_id == audience_id,
                    TopicAlert.is_dismissed == False,  # noqa: E712
                )
                .order_by(TopicAlert.created_at.desc())
                .limit(10)
                .all()
            )
            if not alerts:
                return ""

            lines = ["## RECENT ALERTS"]
            for a in alerts:
                lines.append(
                    f"- [{a.severity}] {a.alert_type}: {a.title} — {a.message}"
                )

            return "\n".join(lines)
        except Exception:
            logger.debug("Failed to collect alerts", exc_info=True)
            return ""

    def _collect_theme_summaries(self, audience_id: UUID) -> str:
        """Coleta resumos narrativos de temas."""
        try:
            from app.modules.theme_analysis.infra.repositories.theme_analysis_repository import (
                ThemeAnalysisRepository,
            )
            from app.modules.theme_analysis.infra.repositories.theme_summary_repository import (
                ThemeSummaryRepository,
            )

            repo = ThemeAnalysisRepository(self.db)
            summary_repo = ThemeSummaryRepository(self.db)
            analysis = repo.find_latest_by_audience_and_window(audience_id, "week")
            if not analysis or analysis.status != "ready":
                return ""

            themes = repo.get_themes(analysis.id)
            if not themes:
                return ""

            lines = ["## THEME NARRATIVES"]
            for t in themes[:3]:
                summary = summary_repo.find_by_theme_id(t.id)
                if summary and summary.narrative:
                    lines.append(f"\n### {t.name}")
                    lines.append(summary.narrative[:500])

            return "\n".join(lines) if len(lines) > 1 else ""
        except Exception:
            logger.debug("Failed to collect theme summaries", exc_info=True)
            return ""
