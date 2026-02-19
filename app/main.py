import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routes import (
    audience_templates_router,
    audiences_router,
    communities_router,
    similar_communities_router,
    topics_router,
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
app.include_router(topics_router)
app.include_router(audiences_router)
app.include_router(audience_templates_router)
app.include_router(similar_communities_router)
app.include_router(communities_router)


@app.get("/")
def root():
    return {"message": "Hello from CRM!!!"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
