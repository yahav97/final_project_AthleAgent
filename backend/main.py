"""
AthleAgent FastAPI Backend
Main application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from utils.logging import logger

# Import all models to register them
from models import (
    User, Team, TeamMember, JoinRequest,
    DailyRecord, Prediction, NutritionRecord,
    StressSurvey, HealthConnectPermission, Injury
)

# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Smart injury risk prediction system using ML"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info("Database models loaded")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down server")


@app.get("/")
async def root():
    """Root endpoint - health check."""
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Import and register API routes
from api.routes import auth

# Register authentication routes
app.include_router(
    auth.router,
    prefix=settings.API_V1_PREFIX + "/auth",
    tags=["Authentication"],
)

# TODO: Add other route imports when ready
# from api.routes import predictions, daily_data, nutrition, teams
# app.include_router(predictions.router, prefix=settings.API_V1_PREFIX + "/predictions", tags=["Predictions"])
# app.include_router(daily_data.router, prefix=settings.API_V1_PREFIX + "/daily-data", tags=["Daily Data"])
# app.include_router(nutrition.router, prefix=settings.API_V1_PREFIX + "/nutrition", tags=["Nutrition"])
# app.include_router(teams.router, prefix=settings.API_V1_PREFIX + "/teams", tags=["Teams"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        # reload=True causes the watchfiles spam; we keep it off for cleaner logs
        reload=False,
        # show only warnings/errors from uvicorn & watchfiles
        log_level="warning",
    )