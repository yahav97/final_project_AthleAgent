"""Root and liveness routes."""

from fastapi import APIRouter

from config import settings

router = APIRouter(tags=["Health"])


@router.get("/")
async def root():
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


@router.get("/health")
async def health_check():
    return {"status": "healthy"}
