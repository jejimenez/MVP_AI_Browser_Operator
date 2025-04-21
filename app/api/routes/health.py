# app/api/routes/health.py

from fastapi import APIRouter, Depends
from typing import Dict

from app.schemas.responses import HealthResponse
from app.api.dependencies import get_health_checker

router = APIRouter()

@router.get(
    "",
    response_model=HealthResponse,
    summary="Health check",
    description="Check the health status of the service"
)
async def health_check(
    health_checker = Depends(get_health_checker)
) -> HealthResponse:
    """Check service health status."""
    status = await health_checker.check()
    return HealthResponse(
        status="healthy" if status else "unhealthy",
        version="1.0.0",
        components=status
    )