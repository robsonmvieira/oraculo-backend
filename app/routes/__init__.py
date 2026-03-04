"""Routes package for the CRM API."""

from app.routes.auth import router as auth_router
from app.routes.topics import router as topics_router
from app.routes.audiences import router as audiences_router
from app.routes.audience_templates import router as audience_templates_router
from app.routes.audience_topics import router as audience_topics_router
from app.routes.audience_keywords import router as audience_keywords_router
from app.routes.similar_communities import router as similar_communities_router
from app.routes.communities import router as communities_router
from app.routes.topic_deep_dive import router as topic_deep_dive_router
from app.routes.topic_patterns import router as topic_patterns_router
from app.routes.topic_sentiment import router as topic_sentiment_router
from app.routes.topic_behavioral_patterns import (
    router as topic_behavioral_patterns_router,
)
from app.routes.topic_snapshots import router as topic_snapshots_router
from app.routes.notifications import router as notifications_router
from app.routes.topic_ask import router as topic_ask_router
from app.routes.topic_chat import router as topic_chat_router
from app.routes.theme_analysis import router as theme_analysis_router
from app.routes.intent_classification import router as intent_classification_router
from app.routes.topic_alerts import router as topic_alerts_router
from app.routes.content_suggestions import router as content_suggestions_router
from app.routes.intent_ask import router as intent_ask_router
from app.routes.intent_chat import router as intent_chat_router
from app.routes.semantic_search import router as semantic_search_router
from app.routes.youtube_validation import router as youtube_validation_router

__all__ = [
    "auth_router",
    "topics_router",
    "audiences_router",
    "audience_templates_router",
    "audience_topics_router",
    "audience_keywords_router",
    "similar_communities_router",
    "communities_router",
    "topic_deep_dive_router",
    "topic_patterns_router",
    "topic_sentiment_router",
    "topic_behavioral_patterns_router",
    "topic_snapshots_router",
    "notifications_router",
    "topic_ask_router",
    "topic_chat_router",
    "theme_analysis_router",
    "intent_classification_router",
    "topic_alerts_router",
    "content_suggestions_router",
    "intent_ask_router",
    "intent_chat_router",
    "semantic_search_router",
    "youtube_validation_router",
]
