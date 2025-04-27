# app/api/routes/__init__.py
from fastapi import APIRouter
from .operator_execution import router as operator_router
from .health import router as health_router

# Main router that combines all sub-routers
api_router = APIRouter()

# Include all sub-routers with their prefixes
api_router.include_router(operator_router, prefix="/operator", tags=["Operator Execution"])
api_router.include_router(health_router, prefix="/health", tags=["Health Checks"])