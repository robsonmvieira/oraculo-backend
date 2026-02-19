from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import audiences_router, audience_templates_router, topics_router

app = FastAPI(
    title="CRM API",
    description="API para gerenciamento de leads e propostas",
    version="0.1.0",
)

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


@app.get("/")
def root():
    return {"message": "Hello from CRM!!!"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
