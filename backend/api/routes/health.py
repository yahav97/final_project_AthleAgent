"""Root and liveness routes."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from config import settings
from schemas.enums import HealthStatus
from services.health_status import build_health_report, health_http_status_code

router = APIRouter(tags=["Health"])


@router.get("/")
async def root():
    return {
        "status": HealthStatus.OK.value,
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


@router.get("/health")
async def health_check():
    """
    Readiness probe: Firestore client and gated ML model must both be available.

    Returns 503 when POST /predict/daily cannot serve (missing Firestore or blocked model).
    """
    report = build_health_report()
    return JSONResponse(status_code=health_http_status_code(report), content=report)
