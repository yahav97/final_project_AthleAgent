"""
AthleAgent FastAPI Backend
Main application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from middleware.request_logging import RequestLoggingMiddleware
from utils.exceptions import register_exception_handlers
from utils.logging import logger

from api.routes.health import router as health_router
from api.routes.observability import router as observability_router
from api.routes.predict import router as predict_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load gated model on startup; log shutdown."""
    from ml.model_loader import load_model

    load_model(settings.MODEL_PATH)
    logger.info(
        "Starting %s v%s (Firestore-backed inference)",
        settings.PROJECT_NAME,
        settings.VERSION,
        extra={"event": "server_startup"},
    )
    yield
    logger.info("Shutting down server", extra={"event": "server_shutdown"})


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Smart injury risk prediction system using ML",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(health_router)
app.include_router(predict_router)
app.include_router(observability_router)
register_exception_handlers(app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
        log_level="warning",
    )
