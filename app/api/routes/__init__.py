# app/api/routes/__init__.py
from fastapi import APIRouter
from .test_execution import router as test_router
from .health import router as health_router

# Main router that combines all sub-routers
api_router = APIRouter()

# Include all sub-routers with their prefixes
api_router.include_router(test_router, prefix="/tests", tags=["Test Execution"])
api_router.include_router(health_router, prefix="/health", tags=["Health Checks"])