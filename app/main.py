import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routes import (
    auth_router,
    audience_keywords_router,
    audience_templates_router,
    audience_topics_router,
    audiences_router,
    communities_router,
    notifications_router,
    similar_communities_router,
    topic_behavioral_patterns_router,
    topic_deep_dive_router,
    topic_patterns_router,
    topic_sentiment_router,
    topic_ask_router,
    theme_analysis_router,
    intent_classification_router,
    topic_alerts_router,
    topic_chat_router,
    topic_snapshots_router,
    topics_router,
    content_suggestions_router,
    intent_ask_router,
    intent_chat_router,
    semantic_search_router,
    youtube_validation_router,
    product_intelligence_router,
)

logging.basicConfig(
    level=logging.DEBUG if settings.debug == "1" else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("oracle")

app = FastAPI(
    title="Oracle API",
    description="API para analisar comunidades do Reddit",
    version="0.1.0",
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled error on %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    body: dict = {
        "detail": "Internal Server Error",
    }
    if settings.app_env == "development":
        body["error"] = str(exc)
        body["traceback"] = traceback.format_exception(exc)
    return JSONResponse(status_code=500, content=body)


# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(topics_router)
app.include_router(audiences_router)
app.include_router(audience_templates_router)
app.include_router(topic_patterns_router)
app.include_router(topic_sentiment_router)
app.include_router(audience_topics_router)
app.include_router(audience_keywords_router)
app.include_router(similar_communities_router)
app.include_router(communities_router)
app.include_router(topic_deep_dive_router)
app.include_router(topic_behavioral_patterns_router)
app.include_router(topic_snapshots_router)
app.include_router(notifications_router)
app.include_router(topic_ask_router)
app.include_router(topic_chat_router)
app.include_router(theme_analysis_router)
app.include_router(intent_classification_router)
app.include_router(topic_alerts_router)
app.include_router(content_suggestions_router)
app.include_router(intent_ask_router)
app.include_router(intent_chat_router)
app.include_router(semantic_search_router)
app.include_router(youtube_validation_router)
app.include_router(product_intelligence_router)


@app.get("/")
def root():
    return {"message": "Hello from CRM!!!"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
