"""Routes package for the CRM API."""

from app.routes.topics import router as topics_router
from app.routes.audiences import router as audiences_router
from app.routes.audience_templates import router as audience_templates_router
from app.routes.similar_communities import router as similar_communities_router
from app.routes.communities import router as communities_router

__all__ = [
    "topics_router",
    "audiences_router",
    "audience_templates_router",
    "similar_communities_router",
    "communities_router",
]
