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
from app.routes.topic_behavioral_patterns import router as topic_behavioral_patterns_router
from app.routes.notifications import router as notifications_router

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
    "topic_behavioral_patterns_router",
    "notifications_router",
]
