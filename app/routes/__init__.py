"""Routes package for the CRM API."""

from app.routes.topics import router as topics_router
from app.routes.audiences import router as audiences_router
from app.routes.audience_templates import router as audience_templates_router

__all__ = ["topics_router", "audiences_router", "audience_templates_router"]
