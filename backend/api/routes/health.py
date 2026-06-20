"""Root and liveness routes."""

from fastapi import APIRouter

from config import settings
from schemas.enums import HealthStatus

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
    return {"status": HealthStatus.HEALTHY.value}
