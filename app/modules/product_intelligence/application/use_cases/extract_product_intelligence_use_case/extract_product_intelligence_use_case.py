"""Use case de extração de Product Intelligence (executa em background)."""

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audiences.infra.repositories.audience_repository import (
    AudienceRepository,
)
from app.modules.notifications.application.services.notification_event_service import (
    NotificationEventService,
)
from app.modules.product_intelligence.application.use_cases.extract_product_intelligence_use_case.agent.product_intelligence_agent import (
    create_product_intelligence_agent,
)
from app.modules.product_intelligence.infra.repositories.product_intelligence_repository import (
    ProductIntelligenceRepository,
)
from app.modules.theme_analysis.infra.repositories.theme_analysis_repository import (
    ThemeAnalysisRepository,
)

logger = logging.getLogger(__name__)


class ExtractProductIntelligenceUseCase:
    """Executa análise de product intelligence em background."""

    def __init__(self, db: Session):
        self.db = db
        self.audience_repo = AudienceRepository(db)
        self.pi_repo = ProductIntelligenceRepository(db)
        self.theme_repo = ThemeAnalysisRepository(db)

    def execute(
        self,
        audience_id: UUID,
        analysis_id: UUID,
        window: str = "week",
        language: str = "en",
    ) -> bool:
        """Executa pipeline completo de extração de product intelligence."""
        try:
            # 1. Validar audiência
            audience = self.audience_repo.find_by_id(audience_id)
            if not audience:
                self.pi_repo.mark_failed(analysis_id, "Audience not found")
                return False

            communities = self.audience_repo.get_communities(audience_id)
            community_names = [c.subreddit_name for c in communities]

            # 2. Buscar posts da ThemeAnalysis mais recente
            theme_analysis = self.theme_repo.find_latest_by_audience_and_window(
                audience_id, window
            )
            if not theme_analysis or theme_analysis.status != "ready":
                self.pi_repo.mark_failed(
                    analysis_id,
                    "No ready theme analysis found. Run theme analysis first.",
                )
                return False

            theme_posts = self.theme_repo.get_posts(theme_analysis.id)
            if not theme_posts:
                self.pi_repo.mark_failed(
                    analysis_id,
                    "No posts found in theme analysis.",
                )
                return False

            posts_data = [
                {
                    "title": p.title,
                    "selftext": p.selftext or "",
                    "subreddit": p.subreddit,
                    "score": p.score or 0,
                    "num_comments": p.num_comments or 0,
                    "permalink": p.permalink or "",
                    "created_utc": p.created_utc or 0,
                }
                for p in theme_posts
            ]

            # 3. Coletar dados de enriquecimento (opcional, graceful)
            existing_deep_dive_products = self._collect_deep_dive_products(audience_id)
            existing_tool_patterns = self._collect_tool_patterns(audience_id)
            existing_solution_requests = self._collect_solution_requests(
                audience_id, window
            )

            # 4. Executar agente LangGraph
            agent = create_product_intelligence_agent()
            result = agent.invoke(
                {
                    "audience_name": audience.name,
                    "community_names": community_names,
                    "language": language,
                    "posts": posts_data,
                    "existing_deep_dive_products": existing_deep_dive_products,
                    "existing_tool_patterns": existing_tool_patterns,
                    "existing_solution_requests": existing_solution_requests,
                    "enrichment_context": None,
                    "extracted_products": None,
                    "product_profiles": None,
                    "product_opportunities": None,
                }
            )

            product_profiles = result.get("product_profiles") or []
            product_opportunities = result.get("product_opportunities") or []

            if not product_profiles:
                self.pi_repo.mark_failed(
                    analysis_id, "No products could be extracted from posts."
                )
                return False

            # 5. Salvar no banco
            self.pi_repo.save_product_profiles(analysis_id, product_profiles)
            self.pi_repo.save_product_opportunities(analysis_id, product_opportunities)

            # 6. Marcar como pronto
            total_mentions = sum(p.get("total_mentions", 0) for p in product_profiles)
            self.pi_repo.mark_ready(
                analysis_id,
                total_products=len(product_profiles),
                total_mentions=total_mentions,
            )

            # 7. Limpar análises antigas
            self.pi_repo.delete_old_analyses(audience_id, keep_latest=2)

            # 8. Notificar usuário
            try:
                NotificationEventService(self.db).notify_analysis_complete(
                    user_id=audience.user_id,
                    analysis_type="product_intelligence",
                    analysis_id=analysis_id,
                    audience_id=audience_id,
                    audience_name=audience.name,
                )
            except Exception:
                logger.warning(
                    "Failed to send notification for analysis %s",
                    analysis_id,
                    exc_info=True,
                )

            logger.info(
                "Product intelligence complete: %d products, %d opportunities (audience %s)",
                len(product_profiles),
                len(product_opportunities),
                audience_id,
            )
            return True

        except Exception as e:
            logger.exception("Product intelligence failed for audience %s", audience_id)
            self.pi_repo.mark_failed(analysis_id, str(e))
            try:
                audience = self.audience_repo.find_by_id(audience_id)
                if audience:
                    NotificationEventService(self.db).notify_analysis_failed(
                        user_id=audience.user_id,
                        analysis_type="product_intelligence",
                        analysis_id=analysis_id,
                        audience_id=audience_id,
                        audience_name=audience.name,
                        error_message=str(e),
                    )
            except Exception:
                logger.warning("Failed to send failure notification", exc_info=True)
            return False

    def _collect_deep_dive_products(self, audience_id: UUID) -> list[dict] | None:
        """Coleta mentioned_products de todas as deep dives prontas."""
        try:
            from app.modules.topic_deep_dive.domain.entities.topic_deep_dive import (
                TopicDeepDive,
                TopicDeepDiveAnalysis,
            )

            results = (
                self.db.query(TopicDeepDive.mentioned_products)
                .join(TopicDeepDiveAnalysis)
                .filter(
                    TopicDeepDiveAnalysis.audience_id == audience_id,
                    TopicDeepDiveAnalysis.status == "ready",
                    TopicDeepDive.mentioned_products.isnot(None),
                )
                .all()
            )
            products: list[dict] = []
            for (mentioned,) in results:
                if isinstance(mentioned, list):
                    products.extend(mentioned)
            return products if products else None
        except Exception:
            logger.debug("Could not collect deep dive products", exc_info=True)
            return None

    def _collect_tool_patterns(self, audience_id: UUID) -> list[dict] | None:
        """Coleta tool_patterns de todas as análises comportamentais prontas."""
        try:
            from app.modules.topic_behavioral_patterns.domain.entities.topic_behavioral_pattern import (
                TopicBehavioralPattern,
                TopicBehavioralPatternAnalysis,
            )

            results = (
                self.db.query(TopicBehavioralPattern.tool_patterns)
                .join(TopicBehavioralPatternAnalysis)
                .filter(
                    TopicBehavioralPatternAnalysis.audience_id == audience_id,
                    TopicBehavioralPatternAnalysis.status == "ready",
                    TopicBehavioralPattern.tool_patterns.isnot(None),
                )
                .all()
            )
            patterns: list[dict] = []
            for (tools,) in results:
                if isinstance(tools, list):
                    patterns.extend(tools)
            return patterns if patterns else None
        except Exception:
            logger.debug("Could not collect tool patterns", exc_info=True)
            return None

    def _collect_solution_requests(
        self, audience_id: UUID, window: str
    ) -> list[dict] | None:
        """Coleta posts de solution_request da classificação de intents."""
        try:
            from app.modules.intent_classification.domain.entities.intent_classification import (
                IntentClassificationAnalysis,
                PostIntentClassification,
            )

            analysis = (
                self.db.query(IntentClassificationAnalysis)
                .filter(
                    IntentClassificationAnalysis.audience_id == audience_id,
                    IntentClassificationAnalysis.time_window == window,
                    IntentClassificationAnalysis.status == "ready",
                )
                .order_by(IntentClassificationAnalysis.created_at.desc())
                .first()
            )
            if not analysis:
                return None

            posts = (
                self.db.query(
                    PostIntentClassification.title,
                    PostIntentClassification.subreddit,
                )
                .filter(
                    PostIntentClassification.analysis_id == analysis.id,
                    PostIntentClassification.primary_intent == "solution_request",
                )
                .limit(30)
                .all()
            )
            if not posts:
                return None

            return [
                {"title": title, "subreddit": subreddit} for title, subreddit in posts
            ]
        except Exception:
            logger.debug("Could not collect solution requests", exc_info=True)
            return None
