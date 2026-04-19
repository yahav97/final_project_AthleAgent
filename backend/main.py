"""
AthleAgent FastAPI Backend
Main application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from utils.logging import logger

from api.routes.health import router as health_router
from api.routes.predict import router as predict_router

# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Smart injury risk prediction system using ML",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(predict_router)


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    from ml.model_loader import load_model

    load_model(settings.MODEL_PATH)
    logger.info("Starting %s v%s", settings.PROJECT_NAME, settings.VERSION)
    if settings.ENABLE_LEGACY_AUTH_DB:
        logger.info("Legacy auth + Postgres routes are enabled.")
    else:
        logger.info("Inference mode: legacy auth DB routes are disabled (ENABLE_LEGACY_AUTH_DB=false).")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down server")


if settings.ENABLE_LEGACY_AUTH_DB:
    from api.routes.auth import router as auth_router

    app.include_router(
        auth_router,
        prefix=settings.API_V1_PREFIX + "/auth",
        tags=["Authentication"],
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="warning",
    )
